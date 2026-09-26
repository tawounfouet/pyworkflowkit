"""Concurrent workflow coordinator with serialized runtime-state authority."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.application.capacity import CapacityLease, CapacityManager
from pyworkflowkit.application.completion import AttemptCompletion, ExecutionHandle
from pyworkflowkit.application.events import RuntimeEventFactory
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.observability import LogContext, log_runtime
from pyworkflowkit.application.planning import build_dependency_graph
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    TASK_TERMINAL_STATUSES,
    RuntimeEventType,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.graph import DependencyGraph
from pyworkflowkit.domain.ids import TaskId
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.errors import ExecutorError, RuntimeInvariantError, TaskExecutionError
from pyworkflowkit.ports.executor import RunContext, TaskHandler
from pyworkflowkit.ports.metadata_store import MetadataStore
from pyworkflowkit.ports.runtime import Clock, RuntimeIdFactory, Sleeper

logger = logging.getLogger("pyworkflowkit.concurrent_runner")


@dataclass(slots=True)
class _ActiveExecution:
    task_id: TaskId
    task_run: TaskRun
    attempt: TaskAttempt
    lease: CapacityLease
    handle: ExecutionHandle


@dataclass(frozen=True, slots=True)
class _PendingRetry:
    task_id: TaskId
    next_attempt_number: int


class ConcurrentRunner(Runner):
    """Coordinate bounded parallel execution while serializing state transitions."""

    def __init__(
        self,
        *,
        metadata_store: MetadataStore,
        handler_registry: HandlerRegistry,
        executor: ThreadExecutor,
        clock: Clock,
        id_factory: RuntimeIdFactory,
        sleeper: Sleeper,
        global_limit: int | None = None,
        executor_limit: int | None = None,
    ) -> None:
        super().__init__(
            metadata_store=metadata_store,
            handler_registry=handler_registry,
            executor=executor,
            clock=clock,
            id_factory=id_factory,
            sleeper=sleeper,
        )
        self._thread_executor = executor
        self._global_limit = (
            executor.capabilities.max_concurrency if global_limit is None else global_limit
        )
        self._executor_limit = executor_limit

    def run(
        self,
        workflow: WorkflowDefinition,
        *,
        parameters: Mapping[str, object] | None = None,
    ) -> WorkflowRun:
        """Execute one workflow with bounded parallel READY-task dispatch."""

        if len(self._thread_executor.completion_queue) != 0:
            raise RuntimeInvariantError(
                reason="ThreadExecutor completion queue must be empty before a workflow run"
            )

        graph = build_dependency_graph(workflow)
        self._validator.validate(workflow, graph)
        plan = self._planner.build_plan(workflow, graph)
        resolved_parameters = self._resolve_parameters(
            workflow=workflow,
            supplied=parameters or {},
        )
        handlers = self._preflight_handlers(workflow)

        run = WorkflowRun(
            run_id=self._id_factory.new_workflow_run_id(),
            workflow_id=workflow.workflow_id,
            workflow_version=workflow.version,
            parameters=resolved_parameters,
            created_at=self._clock.now(),
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

        started_at = self._clock.now()
        self._state_machine.start_workflow(run, at=started_at)
        self._persist_workflow_transition(
            run=run,
            event=event_factory.create(
                event_type=RuntimeEventType.WORKFLOW_STARTED,
                occurred_at=started_at,
            ),
        )
        log_runtime(
            logger,
            logging.INFO,
            "Concurrent workflow run started",
            context=LogContext(
                run_id=str(run.run_id),
                workflow_id=str(run.workflow_id),
            ),
            fields={
                "global_limit": self._global_limit,
                "executor_limit": self._effective_executor_limit(),
            },
        )

        capacity = self._new_capacity_manager()
        task_definitions = {task.task_id: task for task in workflow.tasks}
        outputs_by_task_id: dict[TaskId, object] = {}
        active: dict[str, _ActiveExecution] = {}
        pending_retries: dict[TaskId, _PendingRetry] = {}
        workflow_failed = False

        while True:
            if not workflow_failed:
                self._mark_new_ready_tasks(
                    graph=graph,
                    task_runs_by_task_id=task_runs_by_task_id,
                    event_factory=event_factory,
                )

            self._dispatch_pending_retries(
                run=run,
                graph=graph,
                task_definitions=task_definitions,
                handlers=handlers,
                resolved_parameters=resolved_parameters,
                outputs_by_task_id=outputs_by_task_id,
                task_runs_by_task_id=task_runs_by_task_id,
                pending_retries=pending_retries,
                active=active,
                capacity=capacity,
            )

            if not workflow_failed:
                self._dispatch_ready_tasks(
                    run=run,
                    graph=graph,
                    task_definitions=task_definitions,
                    handlers=handlers,
                    resolved_parameters=resolved_parameters,
                    outputs_by_task_id=outputs_by_task_id,
                    task_runs_by_task_id=task_runs_by_task_id,
                    event_factory=event_factory,
                    active=active,
                    capacity=capacity,
                )

            if active:
                completion = self._thread_executor.completion_queue.get()
                execution = active.pop(completion.handle.handle_id, None)
                if execution is None:
                    raise RuntimeInvariantError(
                        reason=(
                            "received completion for an execution handle "
                            f"not owned by this run: '{completion.handle.handle_id}'"
                        )
                    )
                capacity.release(execution.lease)

                terminal_failure = self._apply_completion(
                    run=run,
                    graph=graph,
                    plan_task_ids=plan.task_ids,
                    task_runs_by_task_id=task_runs_by_task_id,
                    task_definitions=task_definitions,
                    outputs_by_task_id=outputs_by_task_id,
                    execution=execution,
                    completion=completion,
                    pending_retries=pending_retries,
                    event_factory=event_factory,
                    workflow_already_failed=workflow_failed,
                )
                workflow_failed = workflow_failed or terminal_failure
                continue

            if pending_retries:
                raise RuntimeInvariantError(
                    reason="retry is pending but no execution can acquire capacity"
                )

            if workflow_failed:
                return self._metadata_store.get_workflow_run(run.run_id)

            if all(
                task_run.status in TASK_TERMINAL_STATUSES
                for task_run in task_runs_by_task_id.values()
            ):
                if any(
                    task_run.status is TaskRunStatus.FAILED
                    for task_run in task_runs_by_task_id.values()
                ):
                    raise RuntimeInvariantError(
                        reason="failed TaskRun exists without failed workflow state"
                    )
                finished_at = self._clock.now()
                self._state_machine.succeed_workflow(run, at=finished_at)
                self._persist_workflow_transition(
                    run=run,
                    event=event_factory.create(
                        event_type=RuntimeEventType.WORKFLOW_SUCCEEDED,
                        occurred_at=finished_at,
                    ),
                )
                return self._metadata_store.get_workflow_run(run.run_id)

            raise RuntimeInvariantError(
                reason="concurrent runner made no progress with non-terminal tasks remaining"
            )

    def _new_capacity_manager(self) -> CapacityManager:
        per_executor_limits = (
            {self._thread_executor.key: self._executor_limit}
            if self._executor_limit is not None
            else None
        )
        return CapacityManager(
            global_limit=self._global_limit,
            executor_capabilities={
                self._thread_executor.key: self._thread_executor.capabilities,
            },
            per_executor_limits=per_executor_limits,
        )

    def _effective_executor_limit(self) -> int:
        if self._executor_limit is None:
            return self._thread_executor.capabilities.max_concurrency
        return min(
            self._executor_limit,
            self._thread_executor.capabilities.max_concurrency,
        )

    def _mark_new_ready_tasks(
        self,
        *,
        graph: DependencyGraph,
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        event_factory: RuntimeEventFactory,
    ) -> None:
        ready = self._ready_resolver.find_ready(
            graph=graph,
            task_runs_by_task_id=task_runs_by_task_id,
        )
        for task_run in ready:
            self._state_machine.mark_task_ready(task_run)
            self._persist_task_transition(
                task_run=task_run,
                event=event_factory.create(
                    event_type=RuntimeEventType.TASK_READY,
                    occurred_at=self._clock.now(),
                    task_run_id=task_run.task_run_id,
                    task_id=task_run.task_id,
                ),
            )

    def _dispatch_ready_tasks(
        self,
        *,
        run: WorkflowRun,
        graph: DependencyGraph,
        task_definitions: Mapping[TaskId, TaskDefinition],
        handlers: Mapping[TaskId, TaskHandler],
        resolved_parameters: Mapping[str, object],
        outputs_by_task_id: Mapping[TaskId, object],
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        event_factory: RuntimeEventFactory,
        active: dict[str, _ActiveExecution],
        capacity: CapacityManager,
    ) -> None:
        ready_task_ids = tuple(
            sorted(
                (
                    task_id
                    for task_id, task_run in task_runs_by_task_id.items()
                    if task_run.status is TaskRunStatus.READY
                ),
                key=str,
            )
        )
        for task_id in ready_task_ids:
            task_run = task_runs_by_task_id[task_id]
            attempt_id = self._id_factory.new_task_attempt_id(
                task_run_id=task_run.task_run_id,
                attempt_number=1,
            )
            lease = capacity.try_acquire(
                executor_key=self._thread_executor.key,
                attempt_id=attempt_id,
            )
            if lease is None:
                continue

            started_at = self._clock.now()
            self._state_machine.start_task(task_run, at=started_at)
            attempt = TaskAttempt(
                attempt_id=attempt_id,
                task_run_id=task_run.task_run_id,
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
            self._submit_attempt(
                run=run,
                graph=graph,
                task_definition=task_definitions[task_id],
                handler=handlers[task_id],
                task_run=task_run,
                attempt=attempt,
                lease=lease,
                resolved_parameters=resolved_parameters,
                outputs_by_task_id=outputs_by_task_id,
                active=active,
            )

    def _dispatch_pending_retries(
        self,
        *,
        run: WorkflowRun,
        graph: DependencyGraph,
        task_definitions: Mapping[TaskId, TaskDefinition],
        handlers: Mapping[TaskId, TaskHandler],
        resolved_parameters: Mapping[str, object],
        outputs_by_task_id: Mapping[TaskId, object],
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        pending_retries: dict[TaskId, _PendingRetry],
        active: dict[str, _ActiveExecution],
        capacity: CapacityManager,
    ) -> None:
        for task_id in tuple(sorted(pending_retries, key=str)):
            task_run = task_runs_by_task_id[task_id]
            pending = pending_retries[task_id]
            attempt_id = self._id_factory.new_task_attempt_id(
                task_run_id=task_run.task_run_id,
                attempt_number=pending.next_attempt_number,
            )
            lease = capacity.try_acquire(
                executor_key=self._thread_executor.key,
                attempt_id=attempt_id,
            )
            if lease is None:
                continue

            attempt = TaskAttempt(
                attempt_id=attempt_id,
                task_run_id=task_run.task_run_id,
                attempt_number=pending.next_attempt_number,
                started_at=self._clock.now(),
            )
            self._persist_retry_attempt(attempt)
            del pending_retries[task_id]
            self._submit_attempt(
                run=run,
                graph=graph,
                task_definition=task_definitions[task_id],
                handler=handlers[task_id],
                task_run=task_run,
                attempt=attempt,
                lease=lease,
                resolved_parameters=resolved_parameters,
                outputs_by_task_id=outputs_by_task_id,
                active=active,
            )

    def _submit_attempt(
        self,
        *,
        run: WorkflowRun,
        graph: DependencyGraph,
        task_definition: TaskDefinition,
        handler: TaskHandler,
        task_run: TaskRun,
        attempt: TaskAttempt,
        lease: CapacityLease,
        resolved_parameters: Mapping[str, object],
        outputs_by_task_id: Mapping[TaskId, object],
        active: dict[str, _ActiveExecution],
    ) -> None:
        context = RunContext(
            workflow_run_id=run.run_id,
            task_run_id=task_run.task_run_id,
            attempt_id=attempt.attempt_id,
            task_id=task_run.task_id,
            attempt_number=attempt.attempt_number,
            workflow_parameters=resolved_parameters,
            dependency_outputs={
                upstream_task_id: outputs_by_task_id[upstream_task_id]
                for upstream_task_id in graph.upstream_of(task_run.task_id)
            },
        )
        handle = self._thread_executor.submit(
            task=task_definition,
            handler=handler,
            context=context,
        )
        if handle.handle_id in active:
            raise RuntimeInvariantError(
                reason=f"execution handle '{handle.handle_id}' was dispatched twice"
            )
        active[handle.handle_id] = _ActiveExecution(
            task_id=task_run.task_id,
            task_run=task_run,
            attempt=attempt,
            lease=lease,
            handle=handle,
        )

    def _apply_completion(
        self,
        *,
        run: WorkflowRun,
        graph: DependencyGraph,
        plan_task_ids: tuple[TaskId, ...],
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        task_definitions: Mapping[TaskId, TaskDefinition],
        outputs_by_task_id: dict[TaskId, object],
        execution: _ActiveExecution,
        completion: AttemptCompletion,
        pending_retries: dict[TaskId, _PendingRetry],
        event_factory: RuntimeEventFactory,
        workflow_already_failed: bool,
    ) -> bool:
        if completion.handle != execution.handle:
            raise RuntimeInvariantError(
                reason="completion handle does not match active execution identity"
            )

        if completion.succeeded:
            if completion.result is None:
                raise RuntimeInvariantError(
                    reason="successful completion is missing TaskResult"
                )
            self._persist_execution_success(
                task_run=execution.task_run,
                attempt=execution.attempt,
                result=completion.result,
                event=event_factory.create(
                    event_type=RuntimeEventType.TASK_SUCCEEDED,
                    occurred_at=self._clock.now(),
                    task_run_id=execution.task_run.task_run_id,
                    task_id=execution.task_id,
                    attempt_number=execution.attempt.attempt_number,
                ),
            )
            outputs_by_task_id[execution.task_id] = completion.result.output
            return False

        if completion.error is None:
            raise RuntimeInvariantError(reason="failed completion is missing ExecutorError")

        failed_at = self._clock.now()
        error_type, error_message, error_category = _normalize_executor_error(completion.error)
        self._state_machine.fail_attempt(
            execution.attempt,
            at=failed_at,
            error_type=error_type,
            error_message=error_message,
            error_category=error_category,
        )
        decision = self._retry_engine.decide(
            policy=task_definitions[execution.task_id].retry_policy,
            attempt_number=execution.attempt.attempt_number,
            error=completion.error,
        )

        if decision.should_retry and not workflow_already_failed:
            if decision.next_attempt_number is None:
                raise RuntimeInvariantError(
                    reason="retry decision is missing next_attempt_number"
                )
            self._persist_retry_failure(
                attempt=execution.attempt,
                event=event_factory.create(
                    event_type=RuntimeEventType.TASK_RETRYING,
                    occurred_at=failed_at,
                    task_run_id=execution.task_run.task_run_id,
                    task_id=execution.task_id,
                    attempt_number=execution.attempt.attempt_number,
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
            pending_retries[execution.task_id] = _PendingRetry(
                task_id=execution.task_id,
                next_attempt_number=decision.next_attempt_number,
            )
            return False

        if workflow_already_failed:
            self._persist_running_sibling_failure(
                task_run=execution.task_run,
                attempt=execution.attempt,
                event=event_factory.create(
                    event_type=RuntimeEventType.TASK_FAILED,
                    occurred_at=failed_at,
                    task_run_id=execution.task_run.task_run_id,
                    task_id=execution.task_id,
                    attempt_number=execution.attempt.attempt_number,
                    payload={
                        "error_type": error_type,
                        "error_category": error_category,
                    },
                ),
            )
            return False

        self._persist_terminal_failure(
            run=run,
            task_run=execution.task_run,
            attempt=execution.attempt,
            graph=graph,
            plan_task_ids=plan_task_ids,
            task_runs_by_task_id=task_runs_by_task_id,
            event_factory=event_factory,
            error_type=error_type,
            error_category=error_category,
        )
        return True

    def _persist_running_sibling_failure(
        self,
        *,
        task_run: TaskRun,
        attempt: TaskAttempt,
        event: RuntimeEvent,
    ) -> None:
        if attempt.finished_at is None:
            raise RuntimeInvariantError(
                reason="running sibling failure requires a finished TaskAttempt"
            )
        self._state_machine.fail_task(task_run, at=attempt.finished_at)
        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_attempt(attempt)
            uow.save_task_run(task_run)
            uow.add_event(event)
            uow.commit()


def _normalize_executor_error(error: ExecutorError) -> tuple[str, str, str]:
    if isinstance(error, TaskExecutionError):
        return (
            error.error_type,
            error.error_message or error.error_type,
            error.error_category,
        )
    error_type = type(error).__name__
    return error_type, str(error) or error_type, error_type


__all__ = ["ConcurrentRunner"]
