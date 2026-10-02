"""Canonical PyWorkflowKit V2 synchronous workflow runtime."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from pyworkflowkit.authoring.definitions import WorkflowDefinition
from pyworkflowkit.authoring.workloads import RegisteredWorkload
from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.diagnostics.model import Diagnostic, DiagnosticSeverity
from pyworkflowkit.domain.enums import FailurePolicy
from pyworkflowkit.errors import ExecutorNotFoundError, RuntimeInvariantError
from pyworkflowkit.executors import (
    Executor,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from pyworkflowkit.persistence import MetadataStore
from pyworkflowkit.planning import ExecutionPlan, TaskPlanEntry, WorkflowPlanner
from pyworkflowkit.runtime._attempts import next_task_attempt
from pyworkflowkit.runtime._readiness import descendants_of, evaluate_readiness
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.entities import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.runtime.identity import TaskAttemptId, WorkflowRunId
from pyworkflowkit.runtime.results import TaskOutcome, WorkflowResult
from pyworkflowkit.runtime.services import (
    Clock,
    RuntimeIdentityFactory,
    SystemClock,
    UuidRuntimeIdentityFactory,
)
from pyworkflowkit.states import (
    SkipReason,
    TaskAttemptStateMachine,
    TaskAttemptStatus,
    TaskRunStateMachine,
    TaskRunStatus,
    WorkflowRunStateMachine,
    WorkflowRunStatus,
)
from pyworkflowkit.states.enums import TASK_RUN_TERMINAL_STATUSES


class WorkflowRuntime:
    """Deterministic synchronous V2 runtime for one explicitly injected executor."""

    def __init__(
        self,
        *,
        executor: Executor,
        metadata: MetadataStore,
        planner: WorkflowPlanner | None = None,
        clock: Clock | None = None,
        identity_factory: RuntimeIdentityFactory | None = None,
    ) -> None:
        if not isinstance(executor, Executor):
            raise TypeError("executor must satisfy the V2 Executor Protocol")
        if not isinstance(metadata, MetadataStore):
            raise TypeError("metadata must satisfy the V2 MetadataStore Protocol")
        self._executor = executor
        self._metadata = metadata
        self._planner = planner or WorkflowPlanner()
        self._clock = clock or SystemClock()
        self._identity_factory = identity_factory or UuidRuntimeIdentityFactory()
        self._workflow_states = WorkflowRunStateMachine()
        self._task_states = TaskRunStateMachine()
        self._attempt_states = TaskAttemptStateMachine()

    def run(
        self,
        workflow: WorkflowDefinition | ExecutionPlan,
        *,
        correlation: CorrelationContext | None = None,
    ) -> WorkflowResult:
        plan = self._compile(workflow)
        self._preflight(plan)

        run_id = self._identity_factory.new_workflow_run_id()
        bound_correlation = _bind_workflow_correlation(
            correlation
            or CorrelationContext(
                correlation_id=self._identity_factory.new_correlation_id(),
            ),
            run_id=run_id,
        )
        created_at = self._now()
        run = WorkflowRun(
            run_id=run_id,
            workflow_name=plan.workflow_name,
            workflow_version=plan.workflow_version,
            definition_fingerprint=plan.definition_fingerprint,
            plan_fingerprint=plan.fingerprint(),
            correlation=bound_correlation,
            created_at=created_at,
        )
        self._metadata.create_workflow_run(run)

        task_runs: dict[str, TaskRun] = {}
        for entry in plan.tasks:
            task_run = TaskRun(
                task_run_id=self._identity_factory.new_task_run_id(),
                workflow_run_id=run_id,
                task_key=entry.key,
                created_at=created_at,
            )
            self._metadata.create_task_run(task_run)
            task_runs[entry.key] = task_run

        self._transition_workflow(run, WorkflowRunStatus.RUNNING)

        outputs: dict[str, object] = {}
        diagnostics: list[Diagnostic] = list(plan.diagnostics)
        failed_entry: TaskPlanEntry | None = None
        failure: FailureEvidence | None = None

        for entry in plan.tasks:
            persisted_runs = {
                value.task_key: value for value in self._metadata.list_task_runs(run_id)
            }
            current = persisted_runs[entry.key]
            statuses = {key: value.status for key, value in persisted_runs.items()}
            readiness = evaluate_readiness(entry, statuses=statuses)

            if readiness.skip_reason is not None:
                self._transition_task(
                    current,
                    TaskRunStatus.SKIPPED,
                    skip_reason=readiness.skip_reason,
                )
                diagnostics.append(
                    _diagnostic(
                        "PWK-RUNTIME-TRIGGER-SKIP",
                        "task skipped because its trigger rule was not satisfied",
                        run=run,
                        task_run=current,
                        details=(
                            ("task_key", entry.key),
                            ("trigger_rule", entry.trigger_rule.value),
                        ),
                    )
                )
                continue

            if not readiness.ready:
                raise RuntimeInvariantError(
                    reason=f"task {entry.key!r} is not ready in topological execution order"
                )

            self._transition_task(current, TaskRunStatus.READY)
            self._transition_task(current, TaskRunStatus.RUNNING)

            attempt = next_task_attempt(
                current,
                self._metadata.list_task_attempts(current.task_run_id),
                attempt_id=self._identity_factory.new_task_attempt_id(),
                created_at=self._now(),
            )
            self._metadata.append_task_attempt(attempt)
            self._transition_attempt(attempt, TaskAttemptStatus.STARTING)
            self._transition_attempt(attempt, TaskAttemptStatus.RUNNING)

            context = TaskExecutionContext(
                workflow_run_id=run_id,
                task_run_id=current.task_run_id,
                attempt_id=attempt.attempt_id,
                attempt_number=attempt.attempt_number,
                correlation=_bind_task_correlation(
                    bound_correlation,
                    task_run=current,
                    attempt_id=attempt.attempt_id,
                ),
                dependency_outputs={
                    key: outputs[key] for key in entry.dependencies if key in outputs
                },
                workload_parameters=_workload_parameters(entry),
            )
            request = TaskExecutionRequest(
                task_key=entry.key,
                workload=entry.task.workload,
                executor_key=entry.executor_requirement.executor_key,
                context=context,
            )
            result = self._execute(request)
            diagnostics.extend(result.diagnostics)

            if result.succeeded:
                self._transition_attempt(attempt, TaskAttemptStatus.SUCCEEDED)
                self._transition_task(current, TaskRunStatus.SUCCEEDED)
                outputs[entry.key] = result.output
                continue

            failure = result.failure
            if failure is None:  # pragma: no cover - TaskExecutionResult invariant guard
                raise RuntimeInvariantError(
                    reason="failed TaskExecutionResult is missing FailureEvidence"
                )

            self._transition_attempt(
                attempt,
                TaskAttemptStatus.FAILED,
                failure=failure,
            )
            self._transition_task(
                current,
                TaskRunStatus.FAILED,
                failure=failure,
            )
            diagnostics.append(
                _diagnostic(
                    "PWK-RUNTIME-TASK-FAILED",
                    "task execution failed",
                    run=run,
                    task_run=current,
                    attempt_id=attempt.attempt_id,
                    severity=DiagnosticSeverity.ERROR,
                    details=(("task_key", entry.key), ("error_code", failure.error_code)),
                )
            )
            failed_entry = entry
            break

        if failed_entry is not None:
            if plan.failure_policy is not FailurePolicy.FAIL_FAST:
                raise RuntimeInvariantError(
                    reason=f"unsupported failure policy {plan.failure_policy.value}"
                )
            self._apply_fail_fast(
                run=run,
                plan=plan,
                failed_entry=failed_entry,
            )
            self._transition_workflow(
                run,
                WorkflowRunStatus.FAILED,
                failure=failure,
            )
        else:
            self._assert_terminal_task_runs(run_id)
            self._transition_workflow(run, WorkflowRunStatus.SUCCEEDED)

        return self._build_result(
            run_id=run_id,
            outputs=outputs,
            diagnostics=tuple(diagnostics),
        )

    def _compile(self, workflow: WorkflowDefinition | ExecutionPlan) -> ExecutionPlan:
        if isinstance(workflow, WorkflowDefinition):
            return self._planner.compile(workflow)
        if isinstance(workflow, ExecutionPlan):
            return workflow
        raise TypeError("workflow must be WorkflowDefinition or ExecutionPlan")

    def _preflight(self, plan: ExecutionPlan) -> None:
        executor_id = self._executor.descriptor.executor_id
        supported_kinds = frozenset(self._executor.descriptor.supported_workload_kinds)

        for entry in plan.tasks:
            requirement = entry.executor_requirement
            if requirement.executor_key != executor_id:
                raise ExecutorNotFoundError(executor_key=requirement.executor_key)
            if requirement.workload_kind not in supported_kinds:
                raise RuntimeInvariantError(
                    reason=(
                        f"executor {executor_id!r} does not support workload kind "
                        f"{requirement.workload_kind!r}"
                    )
                )
            if entry.retry_policy.max_attempts != 1:
                raise RuntimeInvariantError(
                    reason=(
                        f"task {entry.key!r} requests retry max_attempts="
                        f"{entry.retry_policy.max_attempts}; retry execution starts in LOT-07"
                    )
                )
            if entry.timeout_policy.execution_timeout is not None:
                raise RuntimeInvariantError(
                    reason=(
                        f"task {entry.key!r} requests execution_timeout; "
                        "timeout execution starts in LOT-08"
                    )
                )

    def _execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        try:
            result = self._executor.execute(request)
        except Exception as exc:
            return TaskExecutionResult(
                failure=FailureEvidence(
                    error_code=type(exc).__name__,
                    category=FailureCategory.INTERNAL,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    correlation_id=request.context.correlation.correlation_id,
                    workflow_run_id=str(request.context.workflow_run_id),
                    task_run_id=str(request.context.task_run_id),
                    task_attempt_id=str(request.context.attempt_id),
                    source_component="workflow_runtime.executor",
                    message_summary=str(exc) or type(exc).__name__,
                )
            )
        if not isinstance(result, TaskExecutionResult):
            raise RuntimeInvariantError(
                reason="executor returned a value that is not TaskExecutionResult"
            )
        return result

    def _apply_fail_fast(
        self,
        *,
        run: WorkflowRun,
        plan: ExecutionPlan,
        failed_entry: TaskPlanEntry,
    ) -> None:
        descendants = descendants_of(failed_entry.key, plan.tasks)
        for entry in plan.tasks:
            if entry.position <= failed_entry.position:
                continue
            task_run = self._metadata.get_task_run(
                next(
                    value.task_run_id
                    for value in self._metadata.list_task_runs(run.run_id)
                    if value.task_key == entry.key
                )
            )
            if task_run.status not in {TaskRunStatus.PENDING, TaskRunStatus.READY}:
                continue
            reason = (
                SkipReason.DEPENDENCY_FAILED
                if entry.key in descendants
                else SkipReason.FAIL_FAST_ABORT
            )
            self._transition_task(
                task_run,
                TaskRunStatus.SKIPPED,
                skip_reason=reason,
            )

    def _assert_terminal_task_runs(self, run_id: WorkflowRunId) -> None:
        statuses = tuple(task_run.status for task_run in self._metadata.list_task_runs(run_id))
        if not statuses or any(status not in TASK_RUN_TERMINAL_STATUSES for status in statuses):
            raise RuntimeInvariantError(
                reason="workflow exhausted execution plan with non-terminal TaskRuns"
            )
        if any(status in {TaskRunStatus.FAILED, TaskRunStatus.TIMED_OUT} for status in statuses):
            raise RuntimeInvariantError(reason="workflow success path contains failed TaskRuns")

    def _transition_workflow(
        self,
        run: WorkflowRun,
        target: WorkflowRunStatus,
        *,
        failure: FailureEvidence | None = None,
    ) -> None:
        expected = run.status
        at = self._now()
        self._workflow_states.transition(run, target, at=at, failure=failure)
        self._metadata.update_workflow_run(
            run,
            expected_status=expected,
            transitioned_at=at,
        )

    def _transition_task(
        self,
        task_run: TaskRun,
        target: TaskRunStatus,
        *,
        skip_reason: SkipReason | None = None,
        failure: FailureEvidence | None = None,
    ) -> None:
        expected = task_run.status
        at = self._now()
        self._task_states.transition(
            task_run,
            target,
            at=at,
            skip_reason=skip_reason,
            failure=failure,
        )
        self._metadata.update_task_run(
            task_run,
            expected_status=expected,
            transitioned_at=at,
        )

    def _transition_attempt(
        self,
        attempt: TaskAttempt,
        target: TaskAttemptStatus,
        *,
        failure: FailureEvidence | None = None,
    ) -> None:
        expected = attempt.status
        at = self._now()
        self._attempt_states.transition(
            attempt,
            target,
            at=at,
            failure=failure,
        )
        self._metadata.update_task_attempt(
            attempt,
            expected_status=expected,
            transitioned_at=at,
        )

    def _build_result(
        self,
        *,
        run_id: WorkflowRunId,
        outputs: Mapping[str, object],
        diagnostics: tuple[Diagnostic, ...],
    ) -> WorkflowResult:
        run = self._metadata.get_workflow_run(run_id)
        outcomes: list[TaskOutcome] = []

        for task_run in self._metadata.list_task_runs(run_id):
            attempts = self._metadata.list_task_attempts(task_run.task_run_id)
            outcomes.append(
                TaskOutcome(
                    task_key=task_run.task_key,
                    task_run_id=task_run.task_run_id,
                    status=task_run.status,
                    attempt_ids=tuple(attempt.attempt_id for attempt in attempts),
                    output=outputs.get(task_run.task_key),
                    failure=task_run.failure,
                )
            )

        return WorkflowResult(
            run_id=run.run_id,
            status=run.status,
            task_outcomes=tuple(outcomes),
            diagnostics=diagnostics,
            correlation=run.correlation,
            failure=run.failure,
        )

    def _now(self) -> datetime:
        value = self._clock.now()
        if not isinstance(value, datetime):
            raise TypeError("clock.now() must return datetime")
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock.now() must return a timezone-aware datetime")
        return value


def _bind_workflow_correlation(
    correlation: CorrelationContext,
    *,
    run_id: WorkflowRunId,
) -> CorrelationContext:
    return CorrelationContext(
        correlation_id=correlation.correlation_id,
        causation_id=correlation.causation_id,
        parent_execution_id=correlation.parent_execution_id,
        workflow_run_id=str(run_id),
        ingestion_run_id=correlation.ingestion_run_id,
        transformation_execution_id=correlation.transformation_execution_id,
        trace_id=correlation.trace_id,
        span_id=correlation.span_id,
    )


def _bind_task_correlation(
    correlation: CorrelationContext,
    *,
    task_run: TaskRun,
    attempt_id: TaskAttemptId,
) -> CorrelationContext:
    return CorrelationContext(
        correlation_id=correlation.correlation_id,
        causation_id=correlation.causation_id,
        parent_execution_id=correlation.parent_execution_id,
        workflow_run_id=correlation.workflow_run_id,
        task_run_id=str(task_run.task_run_id),
        task_attempt_id=str(attempt_id),
        ingestion_run_id=correlation.ingestion_run_id,
        transformation_execution_id=correlation.transformation_execution_id,
        trace_id=correlation.trace_id,
        span_id=correlation.span_id,
    )


def _workload_parameters(entry: TaskPlanEntry) -> Mapping[str, str]:
    workload = entry.task.workload
    if isinstance(workload, RegisteredWorkload):
        return dict(workload.parameters)
    return {}


def _diagnostic(
    code: str,
    summary: str,
    *,
    run: WorkflowRun,
    task_run: TaskRun,
    attempt_id: TaskAttemptId | None = None,
    severity: DiagnosticSeverity = DiagnosticSeverity.INFO,
    details: tuple[tuple[str, str], ...] = (),
) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=severity,
        summary=summary,
        details=details,
        workflow_run_id=str(run.run_id),
        task_run_id=str(task_run.task_run_id),
        task_attempt_id=(str(attempt_id) if attempt_id is not None else None),
        correlation_id=run.correlation.correlation_id,
        source_component="workflow_runtime",
    )


__all__ = ["WorkflowRuntime"]
