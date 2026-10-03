"""Canonical PyWorkflowKit V2 synchronous workflow runtime."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from threading import RLock

from pyworkflowkit.authoring.definitions import WorkflowDefinition
from pyworkflowkit.authoring.workloads import RegisteredWorkload
from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.diagnostics.inspection import RuntimeInspection, RuntimeInspector
from pyworkflowkit.diagnostics.model import Diagnostic, DiagnosticSeverity
from pyworkflowkit.diagnostics.recovery import RecoveryAssessment
from pyworkflowkit.domain.enums import FailurePolicy
from pyworkflowkit.errors import ExecutorNotFoundError, RuntimeInvariantError
from pyworkflowkit.executors import (
    CancellableExecutor,
    CancellationCapability,
    CancellationStatus,
    Executor,
    TaskCancellationRequest,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from pyworkflowkit.lineage import (
    ExecutionLineage,
    ExecutionLineageProjector,
    RunManifest,
    RunManifestBuilder,
)
from pyworkflowkit.persistence import MetadataStore
from pyworkflowkit.planning import ExecutionPlan, TaskPlanEntry, WorkflowPlanner
from pyworkflowkit.policies.retry import RetryDecision, RetryEvaluator
from pyworkflowkit.runtime._attempts import next_task_attempt
from pyworkflowkit.runtime._readiness import descendants_of, evaluate_readiness
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.entities import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.runtime.evidence import RuntimeEvent, TaskOutputCheckpoint
from pyworkflowkit.runtime.identity import TaskAttemptId, WorkflowRunId
from pyworkflowkit.runtime.reconciliation import (
    ExternalRunVerifier,
    ExternalRunVerifierRegistry,
    ReconciliationReport,
    ReconciliationService,
)
from pyworkflowkit.runtime.references import ExternalRunRef
from pyworkflowkit.runtime.results import CancellationResult, TaskOutcome, WorkflowResult
from pyworkflowkit.runtime.services import (
    Clock,
    RetryWaiter,
    RuntimeIdentityFactory,
    SystemClock,
    SystemRetryWaiter,
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
        retry_evaluator: RetryEvaluator | None = None,
        retry_waiter: RetryWaiter | None = None,
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
        self._retry_evaluator = retry_evaluator or RetryEvaluator()
        self._retry_waiter = retry_waiter or SystemRetryWaiter()
        if not isinstance(self._retry_evaluator, RetryEvaluator):
            raise TypeError("retry_evaluator must be a RetryEvaluator")
        if not isinstance(self._retry_waiter, RetryWaiter):
            raise TypeError("retry_waiter must satisfy RetryWaiter")
        self._workflow_states = WorkflowRunStateMachine()
        self._task_states = TaskRunStateMachine()
        self._attempt_states = TaskAttemptStateMachine()
        self._reconciliation_verifiers = ExternalRunVerifierRegistry()
        self._reconciliation = ReconciliationService(
            metadata=metadata,
            verifier_registry=self._reconciliation_verifiers,
            clock=self._clock,
        )
        self._active_requests: dict[TaskAttemptId, TaskExecutionRequest] = {}
        self._active_requests_lock = RLock()

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

            while True:
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
                    deadline_at=self._execution_deadline(entry),
                )
                self._remember_active_request(request)
                try:
                    result = self._execute(request)
                finally:
                    self._forget_active_request(attempt.attempt_id)

                attempt = self._metadata.get_task_attempt(attempt.attempt_id)
                current = self._metadata.get_task_run(current.task_run_id)
                run = self._metadata.get_workflow_run(run_id)
                diagnostics.extend(result.diagnostics)
                self._persist_external_run_refs(
                    attempt_id=attempt.attempt_id,
                    result=result,
                )

                if attempt.status is TaskAttemptStatus.CANCELLED:
                    if current.status is not TaskRunStatus.CANCELLED:
                        self._transition_task(current, TaskRunStatus.CANCELLED)
                    self._cancel_not_started_tasks(run_id)
                    if run.status in {
                        WorkflowRunStatus.RUNNING,
                        WorkflowRunStatus.CANCELLATION_REQUESTED,
                    }:
                        self._transition_workflow(run, WorkflowRunStatus.CANCELLED)
                    return self._build_result(
                        run_id=run_id,
                        outputs=outputs,
                        diagnostics=tuple(diagnostics),
                    )

                if result.succeeded:
                    self._transition_attempt(attempt, TaskAttemptStatus.SUCCEEDED)
                    self._transition_task(current, TaskRunStatus.SUCCEEDED)
                    outputs[entry.key] = result.output
                    checkpoint_diagnostic = self._persist_output_checkpoint(
                        task_run=current,
                        output=result.output,
                        run=run,
                        attempt_id=attempt.attempt_id,
                    )
                    if checkpoint_diagnostic is not None:
                        diagnostics.append(checkpoint_diagnostic)

                    run = self._metadata.get_workflow_run(run_id)
                    if run.status is WorkflowRunStatus.CANCELLATION_REQUESTED:
                        self._cancel_not_started_tasks(run_id)
                        self._transition_workflow(run, WorkflowRunStatus.CANCELLED)
                        return self._build_result(
                            run_id=run_id,
                            outputs=outputs,
                            diagnostics=tuple(diagnostics),
                        )
                    break

                failure = result.failure
                if failure is None:  # pragma: no cover - TaskExecutionResult invariant guard
                    raise RuntimeInvariantError(
                        reason="failed TaskExecutionResult is missing FailureEvidence"
                    )

                evaluation = self._retry_evaluator.evaluate(
                    policy=entry.retry_policy,
                    failure=failure,
                    attempt_number=attempt.attempt_number,
                    elapsed_seconds=self._task_elapsed_seconds(current),
                )
                diagnostics.append(
                    _retry_diagnostic(
                        evaluation=evaluation,
                        run=run,
                        task_run=current,
                        attempt_id=attempt.attempt_id,
                    )
                )

                if evaluation.decision in {
                    RetryDecision.RECONCILE,
                    RetryDecision.ESCALATE,
                }:
                    uncertain_attempt_status = (
                        TaskAttemptStatus.REQUIRES_RECONCILIATION
                        if evaluation.decision is RetryDecision.RECONCILE
                        else TaskAttemptStatus.UNKNOWN_OUTCOME
                    )
                    self._transition_attempt(
                        attempt,
                        uncertain_attempt_status,
                        failure=failure,
                    )
                    self._transition_task(
                        current,
                        TaskRunStatus.UNKNOWN_OUTCOME,
                        failure=failure,
                    )
                    self._transition_workflow(
                        run,
                        WorkflowRunStatus.UNKNOWN_OUTCOME,
                        failure=failure,
                    )
                    return self._build_result(
                        run_id=run_id,
                        outputs=outputs,
                        diagnostics=tuple(diagnostics),
                    )

                attempt_terminal_status = (
                    TaskAttemptStatus.TIMED_OUT
                    if failure.category is FailureCategory.TIMEOUT
                    else TaskAttemptStatus.CANCELLED
                    if failure.category is FailureCategory.CANCELLED
                    else TaskAttemptStatus.FAILED
                )
                self._transition_attempt(
                    attempt,
                    attempt_terminal_status,
                    failure=failure,
                )

                if evaluation.decision is RetryDecision.RETRY:
                    diagnostics.append(
                        _diagnostic(
                            "PWK-RETRY-SCHEDULED",
                            "new TaskAttempt scheduled by RetryPolicy",
                            run=run,
                            task_run=current,
                            attempt_id=attempt.attempt_id,
                            details=(
                                ("attempt_number", str(attempt.attempt_number)),
                                ("next_attempt_number", str(attempt.attempt_number + 1)),
                                ("delay_seconds", _format_seconds(evaluation.delay_seconds)),
                                ("reason", evaluation.reason),
                            ),
                        )
                    )
                    if evaluation.delay_seconds:
                        self._retry_waiter.wait(evaluation.delay_seconds)
                    continue

                task_terminal_status = (
                    TaskRunStatus.TIMED_OUT
                    if failure.category is FailureCategory.TIMEOUT
                    else TaskRunStatus.CANCELLED
                    if failure.category is FailureCategory.CANCELLED
                    else TaskRunStatus.FAILED
                )
                self._transition_task(
                    current,
                    task_terminal_status,
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
                        details=(
                            ("task_key", entry.key),
                            ("error_code", failure.error_code),
                            ("retry_decision", evaluation.decision.value),
                            ("retry_reason", evaluation.reason),
                        ),
                    )
                )
                failed_entry = entry
                break

            if failed_entry is not None:
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
            workflow_terminal_status = (
                WorkflowRunStatus.TIMED_OUT
                if failure is not None and failure.category is FailureCategory.TIMEOUT
                else WorkflowRunStatus.CANCELLED
                if failure is not None and failure.category is FailureCategory.CANCELLED
                else WorkflowRunStatus.FAILED
            )
            self._transition_workflow(
                run,
                workflow_terminal_status,
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

    def events(self, workflow_run_id: WorkflowRunId) -> tuple[RuntimeEvent, ...]:
        """Return canonical durable runtime events for one workflow run."""

        if not isinstance(workflow_run_id, WorkflowRunId):
            raise TypeError("workflow_run_id must be a WorkflowRunId")
        return tuple(self._metadata.list_runtime_events(workflow_run_id))

    def manifest(
        self,
        workflow_run_id: WorkflowRunId,
        *,
        require_terminal: bool = False,
    ) -> RunManifest:
        """Build a deterministic manifest from durable runtime evidence."""

        if not isinstance(workflow_run_id, WorkflowRunId):
            raise TypeError("workflow_run_id must be a WorkflowRunId")
        return RunManifestBuilder(metadata=self._metadata).build(
            workflow_run_id,
            require_terminal=require_terminal,
        )

    def lineage(
        self,
        workflow: WorkflowDefinition | ExecutionPlan,
        workflow_run_id: WorkflowRunId,
    ) -> ExecutionLineage:
        """Project deterministic execution lineage for one persisted run."""

        if not isinstance(workflow_run_id, WorkflowRunId):
            raise TypeError("workflow_run_id must be a WorkflowRunId")
        return ExecutionLineageProjector(
            metadata=self._metadata,
            planner=self._planner,
        ).project(workflow, workflow_run_id)

    def inspect(
        self,
        workflow: WorkflowDefinition | ExecutionPlan,
        workflow_run_id: WorkflowRunId,
    ) -> RuntimeInspection:
        """Inspect one persisted execution against its canonical plan."""

        if not isinstance(workflow_run_id, WorkflowRunId):
            raise TypeError("workflow_run_id must be a WorkflowRunId")
        return RuntimeInspector(
            metadata=self._metadata,
            planner=self._planner,
        ).inspect(workflow, workflow_run_id)

    def recovery_assessment(self, workflow_run_id: WorkflowRunId) -> RecoveryAssessment:
        """Classify durable recovery evidence without mutating runtime state."""

        if not isinstance(workflow_run_id, WorkflowRunId):
            raise TypeError("workflow_run_id must be a WorkflowRunId")
        return self._reconciliation.assess(workflow_run_id)

    def recovery_candidates(self) -> tuple[RecoveryAssessment, ...]:
        """Discover non-terminal persisted runs requiring recovery attention."""

        return self._reconciliation.discover()

    def register_external_run_verifier(self, verifier: ExternalRunVerifier) -> None:
        """Register one provider-specific external-run verifier."""

        self._reconciliation_verifiers.register(verifier)

    def reconcile_run(self, workflow_run_id: WorkflowRunId) -> ReconciliationReport:
        """Reconcile one durable run using local evidence and registered providers."""

        if not isinstance(workflow_run_id, WorkflowRunId):
            raise TypeError("workflow_run_id must be a WorkflowRunId")
        return self._reconciliation.reconcile(workflow_run_id)

    def cancel(self, workflow_run_id: WorkflowRunId) -> CancellationResult:
        run = self._metadata.get_workflow_run(workflow_run_id)
        if run.status in {
            WorkflowRunStatus.SUCCEEDED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.TIMED_OUT,
        }:
            return CancellationResult(
                status=CancellationStatus.ALREADY_TERMINAL,
                workflow_run_id=workflow_run_id,
                reason="workflow_already_terminal",
            )

        if run.status is WorkflowRunStatus.UNKNOWN_OUTCOME:
            return CancellationResult(
                status=CancellationStatus.UNCONFIRMED,
                workflow_run_id=workflow_run_id,
                reason="workflow_outcome_already_unknown",
            )

        if run.status is not WorkflowRunStatus.CANCELLATION_REQUESTED:
            self._transition_workflow(run, WorkflowRunStatus.CANCELLATION_REQUESTED)

        statuses: list[CancellationStatus] = []
        for task_run in self._metadata.list_task_runs(workflow_run_id):
            if task_run.status in {
                TaskRunStatus.PENDING,
                TaskRunStatus.READY,
                TaskRunStatus.BLOCKED,
            }:
                self._transition_task(task_run, TaskRunStatus.CANCELLED)
                statuses.append(CancellationStatus.CONFIRMED)
            elif task_run.status is TaskRunStatus.RUNNING:
                statuses.append(self.cancel_task(task_run.task_run_id).status)
            elif task_run.status is TaskRunStatus.UNKNOWN_OUTCOME:
                statuses.append(CancellationStatus.UNCONFIRMED)

        run = self._metadata.get_workflow_run(workflow_run_id)
        if CancellationStatus.UNCONFIRMED in statuses:
            if run.status is WorkflowRunStatus.CANCELLATION_REQUESTED:
                self._transition_workflow(run, WorkflowRunStatus.UNKNOWN_OUTCOME)
            return CancellationResult(
                status=CancellationStatus.UNCONFIRMED,
                workflow_run_id=workflow_run_id,
                reason="at_least_one_task_cancellation_unconfirmed",
            )
        if CancellationStatus.REQUESTED in statuses:
            return CancellationResult(
                status=CancellationStatus.REQUESTED,
                workflow_run_id=workflow_run_id,
                reason="cancellation_requested_but_not_confirmed",
            )
        if CancellationStatus.UNSUPPORTED in statuses:
            return CancellationResult(
                status=CancellationStatus.UNSUPPORTED,
                workflow_run_id=workflow_run_id,
                reason="executor_does_not_support_active_task_cancellation",
            )

        if run.status is WorkflowRunStatus.CANCELLATION_REQUESTED:
            self._transition_workflow(run, WorkflowRunStatus.CANCELLED)
        return CancellationResult(
            status=CancellationStatus.CONFIRMED,
            workflow_run_id=workflow_run_id,
            reason="workflow_cancellation_confirmed",
        )

    def cancel_task(self, task_run_id: object) -> CancellationResult:
        from pyworkflowkit.runtime.identity import TaskRunId

        if not isinstance(task_run_id, TaskRunId):
            raise TypeError("task_run_id must be a TaskRunId")

        task_run = self._metadata.get_task_run(task_run_id)
        workflow_run_id = task_run.workflow_run_id

        if task_run.status in {
            TaskRunStatus.SUCCEEDED,
            TaskRunStatus.FAILED,
            TaskRunStatus.SKIPPED,
            TaskRunStatus.CANCELLED,
            TaskRunStatus.TIMED_OUT,
        }:
            return CancellationResult(
                status=CancellationStatus.ALREADY_TERMINAL,
                workflow_run_id=workflow_run_id,
                task_run_id=task_run_id,
                reason="task_run_already_terminal",
            )

        if task_run.status in {
            TaskRunStatus.PENDING,
            TaskRunStatus.READY,
            TaskRunStatus.BLOCKED,
        }:
            self._transition_task(task_run, TaskRunStatus.CANCELLED)
            return CancellationResult(
                status=CancellationStatus.CONFIRMED,
                workflow_run_id=workflow_run_id,
                task_run_id=task_run_id,
                reason="task_never_started_and_is_cancelled",
            )

        if task_run.status is TaskRunStatus.UNKNOWN_OUTCOME:
            return CancellationResult(
                status=CancellationStatus.UNCONFIRMED,
                workflow_run_id=workflow_run_id,
                task_run_id=task_run_id,
                reason="task_outcome_already_unknown",
            )

        attempts = self._metadata.list_task_attempts(task_run_id)
        if not attempts:
            return CancellationResult(
                status=CancellationStatus.UNCONFIRMED,
                workflow_run_id=workflow_run_id,
                task_run_id=task_run_id,
                reason="running_task_has_no_persisted_attempt",
            )
        attempt = attempts[-1]
        if attempt.status in {
            TaskAttemptStatus.SUCCEEDED,
            TaskAttemptStatus.FAILED,
            TaskAttemptStatus.TIMED_OUT,
            TaskAttemptStatus.CANCELLED,
        }:
            return CancellationResult(
                status=CancellationStatus.ALREADY_TERMINAL,
                workflow_run_id=workflow_run_id,
                task_run_id=task_run_id,
                attempt_id=attempt.attempt_id,
                reason="task_attempt_already_terminal",
            )

        if attempt.status is not TaskAttemptStatus.CANCELLATION_REQUESTED:
            self._transition_attempt(attempt, TaskAttemptStatus.CANCELLATION_REQUESTED)

        request = self._active_request(attempt.attempt_id)
        if request is None:
            attempt = self._metadata.get_task_attempt(attempt.attempt_id)
            self._transition_attempt(attempt, TaskAttemptStatus.CANCELLATION_UNCONFIRMED)
            task_run = self._metadata.get_task_run(task_run_id)
            self._transition_task(task_run, TaskRunStatus.UNKNOWN_OUTCOME)
            return CancellationResult(
                status=CancellationStatus.UNCONFIRMED,
                workflow_run_id=workflow_run_id,
                task_run_id=task_run_id,
                attempt_id=attempt.attempt_id,
                reason="active_execution_handle_not_available",
            )

        if (
            self._executor.descriptor.cancellation_capability is CancellationCapability.UNSUPPORTED
            or not isinstance(self._executor, CancellableExecutor)
        ):
            attempt = self._metadata.get_task_attempt(attempt.attempt_id)
            self._transition_attempt(attempt, TaskAttemptStatus.RUNNING)
            return CancellationResult(
                status=CancellationStatus.UNSUPPORTED,
                workflow_run_id=workflow_run_id,
                task_run_id=task_run_id,
                attempt_id=attempt.attempt_id,
                reason="executor_cancellation_unsupported",
            )

        executor_result = self._executor.cancel(
            TaskCancellationRequest(
                workflow_run_id=workflow_run_id,
                task_run_id=task_run_id,
                attempt_id=attempt.attempt_id,
                task_key=task_run.task_key,
                requested_at=self._now(),
            )
        )
        attempt = self._metadata.get_task_attempt(attempt.attempt_id)
        task_run = self._metadata.get_task_run(task_run_id)
        self._append_external_run_refs(
            attempt_id=attempt.attempt_id,
            external_refs=executor_result.external_runs,
        )

        if executor_result.status is CancellationStatus.CONFIRMED:
            self._transition_attempt(attempt, TaskAttemptStatus.CANCELLED)
            self._transition_task(task_run, TaskRunStatus.CANCELLED)
        elif executor_result.status is CancellationStatus.UNCONFIRMED:
            self._transition_attempt(attempt, TaskAttemptStatus.CANCELLATION_UNCONFIRMED)
            self._transition_task(task_run, TaskRunStatus.UNKNOWN_OUTCOME)
        elif executor_result.status in {
            CancellationStatus.UNSUPPORTED,
            CancellationStatus.ALREADY_TERMINAL,
        }:
            self._transition_attempt(attempt, TaskAttemptStatus.RUNNING)

        return CancellationResult(
            status=executor_result.status,
            workflow_run_id=workflow_run_id,
            task_run_id=task_run_id,
            attempt_id=attempt.attempt_id,
            reason=executor_result.reason,
        )

    def _persist_output_checkpoint(
        self,
        *,
        task_run: TaskRun,
        output: object,
        run: WorkflowRun,
        attempt_id: TaskAttemptId,
    ) -> Diagnostic | None:
        try:
            checkpoint = TaskOutputCheckpoint(
                task_run_id=task_run.task_run_id,
                output=output,
                recorded_at=self._now(),
            )
        except (TypeError, ValueError) as exc:
            return _diagnostic(
                "PWK-OUTPUT-NONPORTABLE",
                "task output is process-local and was not checkpointed durably",
                run=run,
                task_run=task_run,
                attempt_id=attempt_id,
                severity=DiagnosticSeverity.WARNING,
                details=(("reason", type(exc).__name__),),
            )

        self._metadata.set_task_output_checkpoint(checkpoint)
        return None

    def _persist_external_run_refs(
        self,
        *,
        attempt_id: TaskAttemptId,
        result: TaskExecutionResult,
    ) -> None:
        refs = list(result.external_runs)
        if result.failure is not None and result.failure.external_run is not None:
            refs.append(result.failure.external_run)

        self._append_external_run_refs(
            attempt_id=attempt_id,
            external_refs=refs,
        )

    def _append_external_run_refs(
        self,
        *,
        attempt_id: TaskAttemptId,
        external_refs: Iterable[ExternalRunRef],
    ) -> None:
        existing = {
            (ref.provider, ref.kind, ref.external_run_id)
            for ref in self._metadata.list_external_run_refs(attempt_id)
        }
        for external_ref in external_refs:
            key = (
                external_ref.provider,
                external_ref.kind,
                external_ref.external_run_id,
            )
            if key in existing:
                continue
            self._metadata.append_external_run_ref(
                attempt_id=attempt_id,
                external_ref=external_ref,
            )
            existing.add(key)

    def _remember_active_request(self, request: TaskExecutionRequest) -> None:
        with self._active_requests_lock:
            self._active_requests[request.context.attempt_id] = request

    def _forget_active_request(self, attempt_id: TaskAttemptId) -> None:
        with self._active_requests_lock:
            self._active_requests.pop(attempt_id, None)

    def _active_request(self, attempt_id: TaskAttemptId) -> TaskExecutionRequest | None:
        with self._active_requests_lock:
            return self._active_requests.get(attempt_id)

    def _cancel_not_started_tasks(self, workflow_run_id: WorkflowRunId) -> None:
        for task_run in self._metadata.list_task_runs(workflow_run_id):
            if task_run.status in {
                TaskRunStatus.PENDING,
                TaskRunStatus.READY,
                TaskRunStatus.BLOCKED,
            }:
                self._transition_task(task_run, TaskRunStatus.CANCELLED)

    def _execution_deadline(self, entry: TaskPlanEntry) -> datetime | None:
        timeout = entry.timeout_policy.execution_timeout
        if timeout is None:
            return None
        return self._now() + timedelta(seconds=timeout)

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
            if (
                entry.retry_policy.max_attempts > 1
                and self._executor.descriptor.performs_implicit_workload_retry
            ):
                raise RuntimeInvariantError(
                    reason=(
                        f"task {entry.key!r} requests workflow retry while executor "
                        f"{executor_id!r} declares implicit workload retry"
                    )
                )
            if (
                entry.timeout_policy.execution_timeout is not None
                and not self._executor.descriptor.supports_execution_timeout
            ):
                raise RuntimeInvariantError(
                    reason=(
                        f"task {entry.key!r} requests execution_timeout but executor "
                        f"{executor_id!r} does not support execution deadlines"
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

    def _task_elapsed_seconds(self, task_run: TaskRun) -> float:
        if task_run.started_at is None:
            raise RuntimeInvariantError(reason="RUNNING TaskRun is missing started_at")
        return max(0.0, (self._now() - task_run.started_at).total_seconds())

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


def _format_seconds(value: float) -> str:
    return format(value, ".12g")


def _retry_diagnostic(
    *,
    evaluation: object,
    run: WorkflowRun,
    task_run: TaskRun,
    attempt_id: TaskAttemptId,
) -> Diagnostic:
    from pyworkflowkit.policies.retry import RetryEvaluation

    if not isinstance(evaluation, RetryEvaluation):
        raise TypeError("evaluation must be RetryEvaluation")
    severity = (
        DiagnosticSeverity.WARNING
        if evaluation.decision in {RetryDecision.RECONCILE, RetryDecision.DO_NOT_RETRY}
        else DiagnosticSeverity.INFO
    )
    details = [
        ("decision", evaluation.decision.value),
        ("reason", evaluation.reason),
        ("attempt_number", str(evaluation.attempt_number)),
        ("max_attempts", str(evaluation.max_attempts)),
        ("delay_seconds", _format_seconds(evaluation.delay_seconds)),
        ("failure_category", evaluation.failure_category.value),
        ("retryability", evaluation.retryability.value),
        ("uncertainty", evaluation.uncertainty.value),
    ]
    if evaluation.budget_remaining_seconds is not None:
        details.append(
            (
                "budget_remaining_seconds",
                _format_seconds(evaluation.budget_remaining_seconds),
            )
        )
    return _diagnostic(
        "PWK-RETRY-DECISION",
        "RetryPolicy evaluated structured FailureEvidence",
        run=run,
        task_run=task_run,
        attempt_id=attempt_id,
        severity=severity,
        details=tuple(details),
    )


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
