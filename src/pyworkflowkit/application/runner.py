"""Sequential embedded workflow runner."""

import logging
from collections.abc import Mapping
from datetime import datetime

from pyworkflowkit.application.events import RuntimeEventFactory
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.failure import FailurePropagator
from pyworkflowkit.application.observability import LogContext, log_runtime
from pyworkflowkit.application.observability_plugins import ObservabilityDispatcher
from pyworkflowkit.application.planning import (
    DAGValidator,
    ExecutionPlanner,
    ReadyTaskResolver,
    build_dependency_graph,
)
from pyworkflowkit.application.reconciliation import (
    ReconciliationDisposition,
    ReconciliationReport,
)
from pyworkflowkit.application.retry import RetryEngine
from pyworkflowkit.application.state_machine import RunStateMachine
from pyworkflowkit.contracts.serialization import normalize_portable_json_value
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    RuntimeEventType,
    TaskAttemptStatus,
    TaskRunStatus,
    TimeoutMode,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.graph import DependencyGraph
from pyworkflowkit.domain.ids import TaskId, WorkflowRunId
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import TaskResult
from pyworkflowkit.errors import (
    ExecutorError,
    ExecutorNotFoundError,
    InvalidHandlerError,
    InvalidWorkflowParametersError,
    MetadataNotFoundError,
    ResumeError,
    RuntimeInvariantError,
    SerializationError,
    TaskExecutionError,
    TimeoutCapabilityError,
)
from pyworkflowkit.ports.executor import Executor, RunContext, TaskHandler, TimeoutCapability
from pyworkflowkit.ports.metadata_store import MetadataStore
from pyworkflowkit.ports.runtime import Clock, RuntimeIdFactory, Sleeper

logger = logging.getLogger("pyworkflowkit.runner")


class Runner:
    """Execute a validated workflow sequentially in the current process."""

    def __init__(
        self,
        *,
        metadata_store: MetadataStore,
        handler_registry: HandlerRegistry,
        executor: Executor,
        clock: Clock,
        id_factory: RuntimeIdFactory,
        sleeper: Sleeper,
        observability: ObservabilityDispatcher | None = None,
    ) -> None:
        self._metadata_store = metadata_store
        self._handler_registry = handler_registry
        self._executor = executor
        self._clock = clock
        self._id_factory = id_factory
        self._sleeper = sleeper
        self._observability = observability or ObservabilityDispatcher()
        self._validator = DAGValidator()
        self._planner = ExecutionPlanner()
        self._ready_resolver = ReadyTaskResolver()
        self._retry_engine = RetryEngine()
        self._failure_propagator = FailurePropagator()
        self._state_machine = RunStateMachine()

    def run(
        self,
        workflow: WorkflowDefinition,
        *,
        parameters: Mapping[str, object] | None = None,
    ) -> WorkflowRun:
        """Run one workflow synchronously and return its final WorkflowRun."""
        graph = build_dependency_graph(workflow)
        self._validator.validate(workflow, graph)
        plan = self._planner.build_plan(workflow, graph)

        resolved_parameters = self._resolve_parameters(
            workflow=workflow,
            supplied=parameters or {},
        )
        handlers = self._preflight_handlers(workflow)
        self._validate_timeout_capabilities(workflow)

        run = WorkflowRun(
            run_id=self._id_factory.new_workflow_run_id(),
            workflow_id=workflow.workflow_id,
            workflow_version=workflow.version,
            parameters=resolved_parameters,
            created_at=self._clock.now(),
        )
        log_runtime(
            logger,
            logging.INFO,
            "Workflow run created",
            context=LogContext(
                run_id=str(run.run_id),
                workflow_id=str(run.workflow_id),
            ),
            fields={"workflow_version": run.workflow_version},
        )
        event_factory = RuntimeEventFactory(
            run_id=run.run_id,
            id_factory=self._id_factory,
        )
        task_runs_by_task_id = self._create_task_runs(
            run=run,
            plan_task_ids=plan.task_ids,
        )
        self._persist_initial_state(
            run=run,
            task_runs_by_task_id=task_runs_by_task_id,
        )

        workflow_started_at = self._clock.now()
        self._state_machine.start_workflow(run, at=workflow_started_at)
        self._persist_workflow_transition(
            run=run,
            event=event_factory.create(
                event_type=RuntimeEventType.WORKFLOW_STARTED,
                occurred_at=workflow_started_at,
            ),
        )

        task_definitions = {task.task_id: task for task in workflow.tasks}
        outputs_by_task_id: dict[TaskId, object] = {}

        for task_id in plan.task_ids:
            task_run = task_runs_by_task_id[task_id]
            persisted_runs = self._load_task_runs_by_task_id(run)
            persisted_task_run = persisted_runs[task_id]

            if not self._ready_resolver.is_ready(
                task_run=persisted_task_run,
                graph=graph,
                task_runs_by_task_id=persisted_runs,
            ):
                raise RuntimeInvariantError(reason=f"planned task '{task_id}' is not runtime-ready")

            task_ready_at = self._clock.now()
            self._state_machine.mark_task_ready(task_run)
            self._persist_task_transition(
                task_run=task_run,
                event=event_factory.create(
                    event_type=RuntimeEventType.TASK_READY,
                    occurred_at=task_ready_at,
                    task_run_id=task_run.task_run_id,
                    task_id=task_id,
                ),
            )

            started_at = self._clock.now()
            self._state_machine.start_task(task_run, at=started_at)
            attempt = self._new_attempt(
                task_run=task_run,
                attempt_number=1,
                started_at=started_at,
            )
            self._persist_task_start(
                task_run=task_run,
                attempt=attempt,
                event=event_factory.create(
                    event_type=RuntimeEventType.TASK_STARTED,
                    occurred_at=started_at,
                    task_run_id=task_run.task_run_id,
                    task_id=task_id,
                    attempt_number=1,
                ),
            )

            task_definition = task_definitions[task_id]
            log_runtime(
                logger,
                logging.INFO,
                "Task execution started",
                context=LogContext(
                    run_id=str(run.run_id),
                    workflow_id=str(run.workflow_id),
                    task_run_id=str(task_run.task_run_id),
                    task_id=str(task_id),
                    attempt_number=1,
                    executor_key=task_definition.executor_key,
                ),
            )
            result = self._execute_with_retry(
                run=run,
                task_run=task_run,
                attempt=attempt,
                task_definition=task_definition,
                handler=handlers[task_id],
                resolved_parameters=resolved_parameters,
                dependency_outputs={
                    upstream_task_id: outputs_by_task_id[upstream_task_id]
                    for upstream_task_id in graph.upstream_of(task_id)
                },
                graph=graph,
                plan_task_ids=plan.task_ids,
                task_runs_by_task_id=task_runs_by_task_id,
                event_factory=event_factory,
            )
            outputs_by_task_id[task_id] = result.output
            log_runtime(
                logger,
                logging.INFO,
                "Task execution succeeded",
                context=LogContext(
                    run_id=str(run.run_id),
                    workflow_id=str(run.workflow_id),
                    task_run_id=str(task_run.task_run_id),
                    task_id=str(task_id),
                    executor_key=task_definition.executor_key,
                ),
            )

        if any(
            task_run.status is not TaskRunStatus.SUCCEEDED
            for task_run in task_runs_by_task_id.values()
        ):
            raise RuntimeInvariantError(
                reason="workflow exhausted its plan before all tasks succeeded"
            )

        workflow_finished_at = self._clock.now()
        self._state_machine.succeed_workflow(run, at=workflow_finished_at)
        self._persist_workflow_transition(
            run=run,
            event=event_factory.create(
                event_type=RuntimeEventType.WORKFLOW_SUCCEEDED,
                occurred_at=workflow_finished_at,
            ),
        )
        log_runtime(
            logger,
            logging.INFO,
            "Workflow run succeeded",
            context=LogContext(
                run_id=str(run.run_id),
                workflow_id=str(run.workflow_id),
            ),
        )
        return self._metadata_store.get_workflow_run(run.run_id)

    def resume(
        self,
        workflow: WorkflowDefinition,
        *,
        run_id: WorkflowRunId,
        reconciliation: ReconciliationReport,
    ) -> WorkflowRun:
        """Resume one stale persisted WorkflowRun without re-executing completed tasks."""

        graph = build_dependency_graph(workflow)
        self._validator.validate(workflow, graph)
        plan = self._planner.build_plan(workflow, graph)

        run = self._metadata_store.get_workflow_run(run_id)
        if run.workflow_id != workflow.workflow_id or run.workflow_version != workflow.version:
            raise ResumeError(
                run_id=str(run_id),
                reason="workflow identity/version does not match persisted run",
            )
        if run.status is not WorkflowRunStatus.RUNNING:
            raise ResumeError(
                run_id=str(run_id),
                reason=f"persisted workflow status is {run.status.value}, expected RUNNING",
            )
        if reconciliation.run_id != str(run_id):
            raise ResumeError(
                run_id=str(run_id),
                reason="reconciliation report belongs to another workflow run",
            )
        if reconciliation.requires_manual_action:
            raise ResumeError(
                run_id=str(run_id),
                reason="reconciliation requires manual action",
            )
        if reconciliation.has_still_running:
            raise ResumeError(
                run_id=str(run_id),
                reason="external work is still running",
            )

        resolved_parameters = self._resolve_parameters(
            workflow=workflow,
            supplied=dict(run.parameters),
        )
        task_runs_by_task_id = self._load_task_runs_by_task_id(run)
        if set(task_runs_by_task_id) != set(plan.task_ids):
            raise ResumeError(
                run_id=str(run_id),
                reason="persisted TaskRun set does not match workflow definition",
            )

        existing_events = tuple(self._metadata_store.list_events(run_id))
        next_sequence = (
            max(
                (event.event_sequence or 0 for event in existing_events),
                default=0,
            )
            + 1
        )
        event_factory = RuntimeEventFactory(
            run_id=run_id,
            id_factory=self._id_factory,
            starting_sequence=next_sequence,
        )

        terminal_after_reconciliation = self._apply_resume_reconciliation(
            run=run,
            reconciliation=reconciliation,
            graph=graph,
            plan_task_ids=plan.task_ids,
            task_runs_by_task_id=task_runs_by_task_id,
            event_factory=event_factory,
        )
        if terminal_after_reconciliation:
            return self._metadata_store.get_workflow_run(run_id)

        task_runs_by_task_id = self._load_task_runs_by_task_id(run)
        execution_task_ids = tuple(
            task_id
            for task_id in plan.task_ids
            if task_runs_by_task_id[task_id].status in {TaskRunStatus.PENDING, TaskRunStatus.READY}
        )
        handlers = self._preflight_resume_handlers(
            workflow=workflow,
            execution_task_ids=execution_task_ids,
        )
        self._validate_resume_timeout_capabilities(
            workflow=workflow,
            execution_task_ids=execution_task_ids,
        )
        task_definitions = {task.task_id: task for task in workflow.tasks}
        outputs_by_task_id: dict[TaskId, object] = {}

        for task_id in plan.task_ids:
            persisted_runs = self._load_task_runs_by_task_id(run)
            task_run = persisted_runs[task_id]

            if task_run.status is TaskRunStatus.SUCCEEDED:
                continue
            if task_run.status not in {TaskRunStatus.PENDING, TaskRunStatus.READY}:
                raise ResumeError(
                    run_id=str(run_id),
                    reason=(
                        f"task '{task_id}' remains in non-resumable status {task_run.status.value}"
                    ),
                )
            if task_run.status is TaskRunStatus.PENDING:
                if not self._ready_resolver.is_ready(
                    task_run=task_run,
                    graph=graph,
                    task_runs_by_task_id=persisted_runs,
                ):
                    raise ResumeError(
                        run_id=str(run_id),
                        reason=f"task '{task_id}' is not runtime-ready during resume",
                    )
            else:
                self._validate_ready_task_dependencies_for_resume(
                    run_id=run_id,
                    task_run=task_run,
                    graph=graph,
                    task_runs_by_task_id=persisted_runs,
                )

            dependency_outputs = self._dependency_outputs_for_resume(
                run_id=run_id,
                task_id=task_id,
                graph=graph,
                task_runs_by_task_id=persisted_runs,
                outputs_by_task_id=outputs_by_task_id,
            )

            if task_run.status is TaskRunStatus.PENDING:
                ready_at = self._clock.now()
                self._state_machine.mark_task_ready(task_run)
                self._persist_task_transition(
                    task_run=task_run,
                    event=event_factory.create(
                        event_type=RuntimeEventType.TASK_READY,
                        occurred_at=ready_at,
                        task_run_id=task_run.task_run_id,
                        task_id=task_id,
                        payload={"recovery": "resume"},
                    ),
                )

            attempts = tuple(self._metadata_store.list_task_attempts(task_run.task_run_id))
            next_attempt_number = (
                max(
                    (attempt.attempt_number for attempt in attempts),
                    default=0,
                )
                + 1
            )
            started_at = self._clock.now()
            self._state_machine.start_task(task_run, at=started_at)
            attempt = self._new_attempt(
                task_run=task_run,
                attempt_number=next_attempt_number,
                started_at=started_at,
            )
            self._persist_task_start(
                task_run=task_run,
                attempt=attempt,
                event=event_factory.create(
                    event_type=RuntimeEventType.TASK_STARTED,
                    occurred_at=started_at,
                    task_run_id=task_run.task_run_id,
                    task_id=task_id,
                    attempt_number=next_attempt_number,
                    payload={"recovery": "resume"},
                ),
            )

            task_definition = task_definitions[task_id]
            result = self._execute_with_retry(
                run=run,
                task_run=task_run,
                attempt=attempt,
                task_definition=task_definition,
                handler=handlers[task_id],
                resolved_parameters=resolved_parameters,
                dependency_outputs=dependency_outputs,
                graph=graph,
                plan_task_ids=plan.task_ids,
                task_runs_by_task_id=self._load_task_runs_by_task_id(run),
                event_factory=event_factory,
            )
            outputs_by_task_id[task_id] = result.output

        final_task_runs = self._load_task_runs_by_task_id(run)
        if any(
            task_run.status is not TaskRunStatus.SUCCEEDED for task_run in final_task_runs.values()
        ):
            raise ResumeError(
                run_id=str(run_id),
                reason="resume exhausted execution plan before all tasks succeeded",
            )

        finished_at = self._clock.now()
        self._state_machine.succeed_workflow(run, at=finished_at)
        self._persist_workflow_transition(
            run=run,
            event=event_factory.create(
                event_type=RuntimeEventType.WORKFLOW_SUCCEEDED,
                occurred_at=finished_at,
                payload={"recovery": "resume"},
            ),
        )
        return self._metadata_store.get_workflow_run(run_id)

    def _apply_resume_reconciliation(
        self,
        *,
        run: WorkflowRun,
        reconciliation: ReconciliationReport,
        graph: DependencyGraph,
        plan_task_ids: tuple[TaskId, ...],
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        event_factory: RuntimeEventFactory,
    ) -> bool:
        if not reconciliation.task_reconciliations:
            return False

        failed_items = tuple(
            item
            for item in reconciliation.task_reconciliations
            if item.disposition is ReconciliationDisposition.CONFIRMED_FAILED
        )
        cancelled_items = tuple(
            item
            for item in reconciliation.task_reconciliations
            if item.disposition is ReconciliationDisposition.CONFIRMED_CANCELLED
        )
        if failed_items and cancelled_items:
            raise ResumeError(
                run_id=str(run.run_id),
                reason="reconciliation contains conflicting FAILED and CANCELLED outcomes",
            )

        task_runs_by_run_id = {
            str(task_run.task_run_id): task_run for task_run in task_runs_by_task_id.values()
        }
        changed_attempts: list[TaskAttempt] = []
        changed_task_runs: list[TaskRun] = []
        events: list[RuntimeEvent] = []
        first_failed_task_run: TaskRun | None = None

        for item in reconciliation.task_reconciliations:
            if item.disposition not in {
                ReconciliationDisposition.CONFIRMED_SUCCEEDED,
                ReconciliationDisposition.CONFIRMED_FAILED,
                ReconciliationDisposition.CONFIRMED_CANCELLED,
            }:
                raise ResumeError(
                    run_id=str(run.run_id),
                    reason=f"reconciliation disposition {item.disposition.value} is not resumable",
                )

            task_run = task_runs_by_run_id.get(item.task_run_id)
            if task_run is None:
                raise ResumeError(
                    run_id=str(run.run_id),
                    reason=f"reconciliation references unknown TaskRun '{item.task_run_id}'",
                )
            if task_run.status is not TaskRunStatus.RUNNING:
                raise ResumeError(
                    run_id=str(run.run_id),
                    reason=(
                        f"reconciliation TaskRun '{item.task_run_id}' is "
                        f"{task_run.status.value}, expected RUNNING"
                    ),
                )

            attempts = tuple(self._metadata_store.list_task_attempts(task_run.task_run_id))
            running_attempts = tuple(
                attempt for attempt in attempts if attempt.status is TaskAttemptStatus.RUNNING
            )
            if len(running_attempts) != 1:
                raise ResumeError(
                    run_id=str(run.run_id),
                    reason=(
                        f"TaskRun '{item.task_run_id}' must have exactly one RUNNING "
                        "attempt for reconciliation"
                    ),
                )
            attempt = running_attempts[0]
            if item.running_attempt_ids != (str(attempt.attempt_id),):
                raise ResumeError(
                    run_id=str(run.run_id),
                    reason=f"reconciliation attempt identity mismatch for '{item.task_run_id}'",
                )

            at = self._clock.now()
            if item.disposition is ReconciliationDisposition.CONFIRMED_SUCCEEDED:
                self._state_machine.succeed_attempt(attempt, at=at)
                self._state_machine.succeed_task(task_run, at=at)
                events.append(
                    event_factory.create(
                        event_type=RuntimeEventType.TASK_SUCCEEDED,
                        occurred_at=at,
                        task_run_id=task_run.task_run_id,
                        task_id=task_run.task_id,
                        attempt_number=attempt.attempt_number,
                        payload={
                            "recovery": "reconciliation",
                            "disposition": item.disposition.value,
                        },
                    )
                )
            elif item.disposition is ReconciliationDisposition.CONFIRMED_FAILED:
                self._state_machine.fail_attempt(
                    attempt,
                    at=at,
                    error_type="ExternalReconciliationFailure",
                    error_message="external workload was confirmed failed during recovery",
                    error_category="reconciliation",
                )
                self._state_machine.fail_task(task_run, at=at)
                if first_failed_task_run is None:
                    first_failed_task_run = task_run
                events.append(
                    event_factory.create(
                        event_type=RuntimeEventType.TASK_FAILED,
                        occurred_at=at,
                        task_run_id=task_run.task_run_id,
                        task_id=task_run.task_id,
                        attempt_number=attempt.attempt_number,
                        payload={
                            "recovery": "reconciliation",
                            "disposition": item.disposition.value,
                            "error_type": "ExternalReconciliationFailure",
                            "error_category": "reconciliation",
                        },
                    )
                )
            else:
                self._state_machine.cancel_attempt(attempt, at=at)
                self._state_machine.cancel_task(task_run, at=at)

            changed_attempts.append(attempt)
            changed_task_runs.append(task_run)

        if first_failed_task_run is not None:
            finished_at = first_failed_task_run.finished_at
            if finished_at is None:
                raise ResumeError(
                    run_id=str(run.run_id),
                    reason="reconciled failure is missing finished_at",
                )
            skip_decisions = self._failure_propagator.plan_fail_fast(
                failed_task_id=first_failed_task_run.task_id,
                graph=graph,
                task_runs_by_task_id=task_runs_by_task_id,
                plan_task_ids=plan_task_ids,
            )
            for decision in skip_decisions:
                skipped = task_runs_by_task_id[decision.task_id]
                self._state_machine.skip_task(
                    skipped,
                    reason=decision.reason,
                    at=finished_at,
                )
                changed_task_runs.append(skipped)
                events.append(
                    event_factory.create(
                        event_type=RuntimeEventType.TASK_SKIPPED,
                        occurred_at=finished_at,
                        task_run_id=skipped.task_run_id,
                        task_id=skipped.task_id,
                        payload={
                            "recovery": "reconciliation",
                            "reason": decision.reason.value,
                            "failed_task_id": str(first_failed_task_run.task_id),
                        },
                    )
                )
            self._state_machine.fail_workflow(run, at=finished_at)
            events.append(
                event_factory.create(
                    event_type=RuntimeEventType.WORKFLOW_FAILED,
                    occurred_at=finished_at,
                    payload={
                        "recovery": "reconciliation",
                        "failed_task_id": str(first_failed_task_run.task_id),
                    },
                )
            )
            self._persist_reconciliation_changes(
                run=run,
                attempts=changed_attempts,
                task_runs=changed_task_runs,
                events=events,
            )
            return True

        if cancelled_items:
            finished_at = self._clock.now()
            for task_run in task_runs_by_task_id.values():
                if task_run.status in {TaskRunStatus.PENDING, TaskRunStatus.READY}:
                    self._state_machine.cancel_task(task_run, at=finished_at)
                    changed_task_runs.append(task_run)
            self._state_machine.cancel_workflow(run, at=finished_at)
            events.append(
                event_factory.create(
                    event_type=RuntimeEventType.WORKFLOW_CANCELLED,
                    occurred_at=finished_at,
                    payload={"recovery": "reconciliation"},
                )
            )
            self._persist_reconciliation_changes(
                run=run,
                attempts=changed_attempts,
                task_runs=changed_task_runs,
                events=events,
            )
            return True

        self._persist_reconciliation_changes(
            run=None,
            attempts=changed_attempts,
            task_runs=changed_task_runs,
            events=events,
        )
        return False

    def _persist_reconciliation_changes(
        self,
        *,
        run: WorkflowRun | None,
        attempts: list[TaskAttempt],
        task_runs: list[TaskRun],
        events: list[RuntimeEvent],
    ) -> None:
        unique_task_runs = {task_run.task_run_id: task_run for task_run in task_runs}
        with self._metadata_store.unit_of_work() as uow:
            for attempt in attempts:
                uow.save_task_attempt(attempt)
            for task_run in unique_task_runs.values():
                uow.save_task_run(task_run)
            if run is not None:
                uow.save_workflow_run(run)
            for event in events:
                uow.add_event(event)
            uow.commit()
        for event in events:
            self._observability.publish(event)

    def _validate_ready_task_dependencies_for_resume(
        self,
        *,
        run_id: WorkflowRunId,
        task_run: TaskRun,
        graph: DependencyGraph,
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
    ) -> None:
        for upstream_task_id in graph.upstream_of(task_run.task_id):
            upstream_run = task_runs_by_task_id.get(upstream_task_id)
            if upstream_run is None or upstream_run.status is not TaskRunStatus.SUCCEEDED:
                status = "missing" if upstream_run is None else upstream_run.status.value
                raise ResumeError(
                    run_id=str(run_id),
                    reason=(
                        f"READY task '{task_run.task_id}' has dependency "
                        f"'{upstream_task_id}' in status {status}"
                    ),
                )

    def _dependency_outputs_for_resume(
        self,
        *,
        run_id: WorkflowRunId,
        task_id: TaskId,
        graph: DependencyGraph,
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        outputs_by_task_id: Mapping[TaskId, object],
    ) -> dict[TaskId, object]:
        outputs: dict[TaskId, object] = {}
        for upstream_task_id in graph.upstream_of(task_id):
            if upstream_task_id in outputs_by_task_id:
                outputs[upstream_task_id] = outputs_by_task_id[upstream_task_id]
                continue

            upstream_run = task_runs_by_task_id[upstream_task_id]
            if upstream_run.status is not TaskRunStatus.SUCCEEDED:
                raise ResumeError(
                    run_id=str(run_id),
                    reason=(
                        f"dependency '{upstream_task_id}' for task '{task_id}' "
                        f"is {upstream_run.status.value}, expected SUCCEEDED"
                    ),
                )
            try:
                outputs[upstream_task_id] = self._metadata_store.get_task_output_checkpoint(
                    upstream_run.task_run_id
                )
            except MetadataNotFoundError as exc:
                raise ResumeError(
                    run_id=str(run_id),
                    reason=(f"dependency '{upstream_task_id}' has no durable output checkpoint"),
                ) from exc
        return outputs

    def _preflight_resume_handlers(
        self,
        *,
        workflow: WorkflowDefinition,
        execution_task_ids: tuple[TaskId, ...],
    ) -> dict[TaskId, TaskHandler]:
        selected = set(execution_task_ids)
        handlers: dict[TaskId, TaskHandler] = {}
        for task in workflow.tasks:
            if task.task_id not in selected:
                continue
            if task.executor_key != self._executor.key:
                raise ExecutorNotFoundError(executor_key=task.executor_key)
            if task.handler_ref is None:
                raise InvalidHandlerError(
                    task_id=task.task_id,
                    reason="handler_ref is required for Runner resume",
                )
            handlers[task.task_id] = self._handler_registry.resolve(task.handler_ref)
        return handlers

    def _validate_resume_timeout_capabilities(
        self,
        *,
        workflow: WorkflowDefinition,
        execution_task_ids: tuple[TaskId, ...],
    ) -> None:
        selected = set(execution_task_ids)
        supported = self._executor.capabilities.timeout
        for task in workflow.tasks:
            if task.task_id not in selected:
                continue
            requested = task.timeout_mode
            if requested is TimeoutMode.NONE:
                continue
            if requested is TimeoutMode.SOFT and supported in {
                TimeoutCapability.SOFT,
                TimeoutCapability.HARD,
            }:
                continue
            if requested is TimeoutMode.HARD and supported is TimeoutCapability.HARD:
                continue
            raise TimeoutCapabilityError(
                task_id=task.task_id,
                requested_mode=requested.value,
                executor_key=self._executor.key,
                supported_mode=supported.value,
            )

    def _execute_with_retry(
        self,
        *,
        run: WorkflowRun,
        task_run: TaskRun,
        attempt: TaskAttempt,
        task_definition: TaskDefinition,
        handler: TaskHandler,
        resolved_parameters: Mapping[str, object],
        dependency_outputs: Mapping[TaskId, object],
        graph: DependencyGraph,
        plan_task_ids: tuple[TaskId, ...],
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        event_factory: RuntimeEventFactory,
    ) -> TaskResult:
        current_attempt = attempt

        while True:
            context = RunContext(
                workflow_run_id=run.run_id,
                task_run_id=task_run.task_run_id,
                attempt_id=current_attempt.attempt_id,
                task_id=task_run.task_id,
                attempt_number=current_attempt.attempt_number,
                workflow_parameters=resolved_parameters,
                dependency_outputs=dependency_outputs,
            )

            try:
                result = self._executor.execute(
                    task=task_definition,
                    handler=handler,
                    context=context,
                )
            except ExecutorError as exc:
                failed_at = self._clock.now()
                error_type, error_message, error_category = _normalize_executor_error(exc)
                self._state_machine.fail_attempt(
                    current_attempt,
                    at=failed_at,
                    error_type=error_type,
                    error_message=error_message,
                    error_category=error_category,
                )

                decision = self._retry_engine.decide(
                    policy=task_definition.retry_policy,
                    attempt_number=current_attempt.attempt_number,
                    error=exc,
                )
                log_runtime(
                    logger,
                    logging.WARNING,
                    "Task attempt failed",
                    context=LogContext(
                        run_id=str(run.run_id),
                        workflow_id=str(run.workflow_id),
                        task_run_id=str(task_run.task_run_id),
                        task_id=str(task_run.task_id),
                        attempt_number=current_attempt.attempt_number,
                        executor_key=task_definition.executor_key,
                    ),
                    fields={
                        "error_type": error_type,
                        "error_category": error_category,
                        "will_retry": decision.should_retry,
                        "delay_seconds": decision.delay_seconds,
                    },
                )
                if decision.should_retry:
                    if decision.next_attempt_number is None:
                        raise RuntimeInvariantError(
                            reason="retry decision is missing next_attempt_number"
                        ) from exc

                    self._persist_retry_failure(
                        attempt=current_attempt,
                        event=event_factory.create(
                            event_type=RuntimeEventType.TASK_RETRYING,
                            occurred_at=failed_at,
                            task_run_id=task_run.task_run_id,
                            task_id=task_run.task_id,
                            attempt_number=current_attempt.attempt_number,
                            payload={
                                "error_type": error_type,
                                "error_category": error_category,
                                "delay_seconds": decision.delay_seconds,
                                "next_attempt_number": decision.next_attempt_number,
                            },
                        ),
                    )

                    if decision.delay_seconds > 0:
                        self._sleeper.sleep(decision.delay_seconds)

                    current_attempt = self._new_attempt(
                        task_run=task_run,
                        attempt_number=decision.next_attempt_number,
                        started_at=self._clock.now(),
                    )
                    self._persist_retry_attempt(current_attempt)
                    continue

                self._persist_terminal_failure(
                    run=run,
                    task_run=task_run,
                    attempt=current_attempt,
                    graph=graph,
                    plan_task_ids=plan_task_ids,
                    task_runs_by_task_id=task_runs_by_task_id,
                    event_factory=event_factory,
                    error_type=error_type,
                    error_category=error_category,
                )
                raise

            self._persist_execution_success(
                task_run=task_run,
                attempt=current_attempt,
                result=result,
                event=event_factory.create(
                    event_type=RuntimeEventType.TASK_SUCCEEDED,
                    occurred_at=self._clock.now(),
                    task_run_id=task_run.task_run_id,
                    task_id=task_run.task_id,
                    attempt_number=current_attempt.attempt_number,
                ),
            )
            return result

    def _validate_timeout_capabilities(self, workflow: WorkflowDefinition) -> None:
        supported = self._executor.capabilities.timeout
        for task in workflow.tasks:
            requested = task.timeout_mode
            if requested is TimeoutMode.NONE:
                continue
            if requested is TimeoutMode.SOFT and supported in {
                TimeoutCapability.SOFT,
                TimeoutCapability.HARD,
            }:
                continue
            if requested is TimeoutMode.HARD and supported is TimeoutCapability.HARD:
                continue
            raise TimeoutCapabilityError(
                task_id=task.task_id,
                requested_mode=requested.value,
                executor_key=self._executor.key,
                supported_mode=supported.value,
            )

    def _resolve_parameters(
        self,
        *,
        workflow: WorkflowDefinition,
        supplied: Mapping[str, object],
    ) -> dict[str, object]:
        declared = {parameter.name: parameter for parameter in workflow.parameters}
        unknown = tuple(sorted(set(supplied) - set(declared)))
        if unknown:
            rendered = ", ".join(unknown)
            raise InvalidWorkflowParametersError(reason=f"unknown workflow parameters: {rendered}")

        resolved: dict[str, object] = {}
        for parameter in workflow.parameters:
            if parameter.name in supplied:
                resolved[parameter.name] = supplied[parameter.name]
            elif parameter.required:
                raise InvalidWorkflowParametersError(
                    reason=f"required workflow parameter '{parameter.name}' is missing"
                )
            else:
                resolved[parameter.name] = parameter.default
        return resolved

    def _preflight_handlers(
        self,
        workflow: WorkflowDefinition,
    ) -> dict[TaskId, TaskHandler]:
        handlers: dict[TaskId, TaskHandler] = {}
        for task in workflow.tasks:
            if task.executor_key != self._executor.key:
                raise ExecutorNotFoundError(executor_key=task.executor_key)
            if task.handler_ref is None:
                raise InvalidHandlerError(
                    task_id=task.task_id,
                    reason="handler_ref is required for Runner execution",
                )
            handlers[task.task_id] = self._handler_registry.resolve(task.handler_ref)
        return handlers

    def _create_task_runs(
        self,
        *,
        run: WorkflowRun,
        plan_task_ids: tuple[TaskId, ...],
    ) -> dict[TaskId, TaskRun]:
        created_at = self._clock.now()
        return {
            task_id: TaskRun(
                task_run_id=self._id_factory.new_task_run_id(
                    run_id=run.run_id,
                    task_id=task_id,
                ),
                run_id=run.run_id,
                task_id=task_id,
                created_at=created_at,
            )
            for task_id in plan_task_ids
        }

    def _new_attempt(
        self,
        *,
        task_run: TaskRun,
        attempt_number: int,
        started_at: datetime,
    ) -> TaskAttempt:
        return TaskAttempt(
            attempt_id=self._id_factory.new_task_attempt_id(
                task_run_id=task_run.task_run_id,
                attempt_number=attempt_number,
            ),
            task_run_id=task_run.task_run_id,
            attempt_number=attempt_number,
            started_at=started_at,
        )

    def _persist_initial_state(
        self,
        *,
        run: WorkflowRun,
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
    ) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.add_workflow_run(run)
            for task_run in task_runs_by_task_id.values():
                uow.add_task_run(task_run)
            uow.commit()

    def _load_task_runs_by_task_id(
        self,
        run: WorkflowRun,
    ) -> dict[TaskId, TaskRun]:
        return {
            task_run.task_id: task_run
            for task_run in self._metadata_store.list_task_runs(run.run_id)
        }

    def _persist_workflow_transition(
        self,
        *,
        run: WorkflowRun,
        event: RuntimeEvent,
    ) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.save_workflow_run(run)
            uow.add_event(event)
            uow.commit()
        self._observability.publish(event)

    def _persist_task_transition(
        self,
        *,
        task_run: TaskRun,
        event: RuntimeEvent,
    ) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_run(task_run)
            uow.add_event(event)
            uow.commit()
        self._observability.publish(event)

    def _persist_task_start(
        self,
        *,
        task_run: TaskRun,
        attempt: TaskAttempt,
        event: RuntimeEvent,
    ) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_run(task_run)
            uow.add_task_attempt(attempt)
            uow.add_event(event)
            uow.commit()
        self._observability.publish(event)

    def _persist_retry_failure(
        self,
        *,
        attempt: TaskAttempt,
        event: RuntimeEvent,
    ) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_attempt(attempt)
            uow.add_event(event)
            uow.commit()
        self._observability.publish(event)

    def _persist_retry_attempt(self, attempt: TaskAttempt) -> None:
        with self._metadata_store.unit_of_work() as uow:
            uow.add_task_attempt(attempt)
            uow.commit()

    def _persist_execution_success(
        self,
        *,
        task_run: TaskRun,
        attempt: TaskAttempt,
        result: TaskResult,
        event: RuntimeEvent,
    ) -> None:
        finished_at = event.occurred_at
        self._state_machine.succeed_attempt(attempt, at=finished_at)
        self._state_machine.succeed_task(task_run, at=finished_at)

        output_checkpoint: object | None = None
        output_checkpoint_available = True
        try:
            output_checkpoint = normalize_portable_json_value(
                result.output,
                path=f"task_result.{task_run.task_run_id}.output",
            )
        except SerializationError:
            output_checkpoint_available = False

        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_attempt(attempt)
            uow.save_task_run(task_run)
            uow.add_event(event)
            if output_checkpoint_available:
                uow.add_task_output_checkpoint(
                    task_run_id=task_run.task_run_id,
                    output=output_checkpoint,
                )
            for artifact in result.artifacts:
                uow.add_artifact(
                    task_run_id=task_run.task_run_id,
                    artifact=artifact,
                )
            for external_ref in result.external_refs:
                uow.add_external_run_ref(
                    task_run_id=task_run.task_run_id,
                    external_ref=external_ref,
                )
            uow.commit()
        self._observability.publish(event)

    def _persist_terminal_failure(
        self,
        *,
        run: WorkflowRun,
        task_run: TaskRun,
        attempt: TaskAttempt,
        graph: DependencyGraph,
        plan_task_ids: tuple[TaskId, ...],
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        event_factory: RuntimeEventFactory,
        error_type: str,
        error_category: str,
    ) -> None:
        if attempt.finished_at is None:
            raise RuntimeInvariantError(reason="terminal failure requires a finished TaskAttempt")
        finished_at = attempt.finished_at

        self._state_machine.fail_task(task_run, at=finished_at)
        skip_decisions = self._failure_propagator.plan_fail_fast(
            failed_task_id=task_run.task_id,
            graph=graph,
            task_runs_by_task_id=task_runs_by_task_id,
            plan_task_ids=plan_task_ids,
        )
        for decision in skip_decisions:
            self._state_machine.skip_task(
                task_runs_by_task_id[decision.task_id],
                reason=decision.reason,
                at=finished_at,
            )
        self._state_machine.fail_workflow(run, at=finished_at)

        events = [
            event_factory.create(
                event_type=RuntimeEventType.TASK_FAILED,
                occurred_at=finished_at,
                task_run_id=task_run.task_run_id,
                task_id=task_run.task_id,
                attempt_number=attempt.attempt_number,
                payload={
                    "error_type": error_type,
                    "error_category": error_category,
                },
            )
        ]
        events.extend(
            event_factory.create(
                event_type=RuntimeEventType.TASK_SKIPPED,
                occurred_at=finished_at,
                task_run_id=task_runs_by_task_id[decision.task_id].task_run_id,
                task_id=decision.task_id,
                payload={
                    "reason": decision.reason.value,
                    "failed_task_id": str(task_run.task_id),
                },
            )
            for decision in skip_decisions
        )
        events.append(
            event_factory.create(
                event_type=RuntimeEventType.WORKFLOW_FAILED,
                occurred_at=finished_at,
                payload={"failed_task_id": str(task_run.task_id)},
            )
        )

        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_attempt(attempt)
            uow.save_task_run(task_run)
            for decision in skip_decisions:
                uow.save_task_run(task_runs_by_task_id[decision.task_id])
            uow.save_workflow_run(run)
            for event in events:
                uow.add_event(event)
            uow.commit()
        for event in events:
            self._observability.publish(event)


def _normalize_executor_error(error: ExecutorError) -> tuple[str, str, str]:
    if isinstance(error, TaskExecutionError):
        return (
            error.error_type,
            error.error_message or error.error_type,
            error.error_category,
        )
    error_type = type(error).__name__
    return error_type, str(error) or error_type, error_type


__all__ = ["Runner"]
