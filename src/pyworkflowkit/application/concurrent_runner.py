"""Concurrent workflow coordinator with serialized runtime-state authority."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from queue import Empty
from time import monotonic
from typing import Protocol, runtime_checkable

from pyworkflowkit.application.cancellation import CancellationController
from pyworkflowkit.application.capacity import CapacityLease, CapacityManager
from pyworkflowkit.application.completion import (
    AttemptCompletion,
    CompletionQueue,
    ExecutionHandle,
)
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
    TimeoutMode,
)
from pyworkflowkit.domain.graph import DependencyGraph
from pyworkflowkit.domain.ids import TaskId
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import TaskResult
from pyworkflowkit.errors import (
    ExecutionTimeoutError,
    ExecutorError,
    RuntimeInvariantError,
    TaskExecutionError,
)
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    ExecutorCapabilities,
    RunContext,
    TaskHandler,
)
from pyworkflowkit.ports.metadata_store import MetadataStore
from pyworkflowkit.ports.runtime import Clock, RuntimeIdFactory, Sleeper

logger = logging.getLogger("pyworkflowkit.concurrent_runner")


class _ConcurrentExecutor(Protocol):
    """Structural contract required by the concurrent coordinator."""

    @property
    def key(self) -> str: ...

    @property
    def capabilities(self) -> ExecutorCapabilities: ...

    @property
    def completion_queue(self) -> CompletionQueue: ...

    def execute(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> TaskResult: ...

    def submit(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> ExecutionHandle: ...


@runtime_checkable
class _HardTerminationExecutor(Protocol):
    def terminate(self, handle: ExecutionHandle) -> bool: ...


@dataclass(slots=True)
class _ActiveExecution:
    task_id: TaskId
    task_run: TaskRun
    attempt: TaskAttempt
    lease: CapacityLease
    handle: ExecutionHandle
    deadline_monotonic: float | None = None
    timed_out: bool = False


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
        executor: _ConcurrentExecutor,
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
        self._concurrent_executor = executor
        self._global_limit = (
            executor.capabilities.max_concurrency if global_limit is None else global_limit
        )
        self._executor_limit = executor_limit

    def run(
        self,
        workflow: WorkflowDefinition,
        *,
        parameters: Mapping[str, object] | None = None,
        cancellation: CancellationController | None = None,
    ) -> WorkflowRun:
        """Execute one workflow with bounded parallel READY-task dispatch."""

        if len(self._concurrent_executor.completion_queue) != 0:
            raise RuntimeInvariantError(
                reason="Executor completion queue must be empty before a workflow run"
            )

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

        cancellation_controller = cancellation or CancellationController()
        capacity = self._new_capacity_manager()
        task_definitions = {task.task_id: task for task in workflow.tasks}
        outputs_by_task_id: dict[TaskId, object] = {}
        active: dict[str, _ActiveExecution] = {}
        pending_retries: dict[TaskId, _PendingRetry] = {}
        workflow_failed = False

        try:
            while True:
                if cancellation_controller.is_requested and not workflow_failed:
                    return self._finish_cancellation(
                        run=run,
                        task_runs_by_task_id=task_runs_by_task_id,
                        active=active,
                        pending_retries=pending_retries,
                        capacity=capacity,
                        event_factory=event_factory,
                        cancellation=cancellation_controller,
                    )

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
                    cancellation=cancellation_controller,
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
                        cancellation=cancellation_controller,
                    )

                if cancellation_controller.is_requested and not workflow_failed:
                    continue

                if active:
                    try:
                        cancellation_poll_seconds = (
                            0.05
                            if self._concurrent_executor.capabilities.cancellation
                            is CancellationCapability.HARD
                            else None
                        )
                        completion = self._concurrent_executor.completion_queue.get(
                            timeout=self._completion_wait_timeout(
                                active,
                                cancellation_poll_seconds=cancellation_poll_seconds,
                            )
                        )
                    except Empty:
                        terminal_failure = self._expire_due_timeouts(
                            run=run,
                            graph=graph,
                            plan_task_ids=plan.task_ids,
                            task_runs_by_task_id=task_runs_by_task_id,
                            task_definitions=task_definitions,
                            active=active,
                            pending_retries=pending_retries,
                            event_factory=event_factory,
                            workflow_already_failed=workflow_failed,
                        )
                        workflow_failed = workflow_failed or terminal_failure
                        continue

                    execution = active.pop(completion.handle.handle_id, None)
                    if execution is None:
                        raise RuntimeInvariantError(
                            reason=(
                                "received completion for an execution handle "
                                f"not owned by this run: '{completion.handle.handle_id}'"
                            )
                        )
                    capacity.release(execution.lease)

                    if execution.timed_out:
                        continue

                    if cancellation_controller.is_requested and not workflow_failed:
                        self._apply_cancellation_completion(
                            execution=execution,
                            completion=completion,
                            event_factory=event_factory,
                        )
                        continue

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
        except KeyboardInterrupt:
            if workflow_failed:
                self._drain_terminal_workflow_attempts(
                    active=active,
                    capacity=capacity,
                    event_factory=event_factory,
                )
                return self._metadata_store.get_workflow_run(run.run_id)

            cancellation_controller.request(reason="keyboard_interrupt")
            return self._finish_cancellation(
                run=run,
                task_runs_by_task_id=task_runs_by_task_id,
                active=active,
                pending_retries=pending_retries,
                capacity=capacity,
                event_factory=event_factory,
                cancellation=cancellation_controller,
            )

    def _new_capacity_manager(self) -> CapacityManager:
        per_executor_limits = (
            {self._concurrent_executor.key: self._executor_limit}
            if self._executor_limit is not None
            else None
        )
        return CapacityManager(
            global_limit=self._global_limit,
            executor_capabilities={
                self._concurrent_executor.key: self._concurrent_executor.capabilities,
            },
            per_executor_limits=per_executor_limits,
        )

    def _effective_executor_limit(self) -> int:
        if self._executor_limit is None:
            return self._concurrent_executor.capabilities.max_concurrency
        return min(
            self._executor_limit,
            self._concurrent_executor.capabilities.max_concurrency,
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
        cancellation: CancellationController,
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
            if cancellation.is_requested:
                return
            task_run = task_runs_by_task_id[task_id]
            attempt_id = self._id_factory.new_task_attempt_id(
                task_run_id=task_run.task_run_id,
                attempt_number=1,
            )
            lease = capacity.try_acquire(
                executor_key=self._concurrent_executor.key,
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
        cancellation: CancellationController,
    ) -> None:
        active_task_ids = {execution.task_id for execution in active.values()}
        for task_id in tuple(sorted(pending_retries, key=str)):
            if cancellation.is_requested:
                return
            if task_id in active_task_ids:
                continue
            task_run = task_runs_by_task_id[task_id]
            pending = pending_retries[task_id]
            attempt_id = self._id_factory.new_task_attempt_id(
                task_run_id=task_run.task_run_id,
                attempt_number=pending.next_attempt_number,
            )
            lease = capacity.try_acquire(
                executor_key=self._concurrent_executor.key,
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
        handle = self._concurrent_executor.submit(
            task=task_definition,
            handler=handler,
            context=context,
        )
        if handle.handle_id in active:
            raise RuntimeInvariantError(
                reason=f"execution handle '{handle.handle_id}' was dispatched twice"
            )
        deadline = (
            monotonic() + task_definition.timeout_seconds
            if task_definition.timeout_mode is not TimeoutMode.NONE
            and task_definition.timeout_seconds is not None
            else None
        )
        active[handle.handle_id] = _ActiveExecution(
            task_id=task_run.task_id,
            task_run=task_run,
            attempt=attempt,
            lease=lease,
            handle=handle,
            deadline_monotonic=deadline,
        )

    @staticmethod
    def _completion_wait_timeout(
        active: Mapping[str, _ActiveExecution],
        *,
        cancellation_poll_seconds: float | None = None,
    ) -> float | None:
        deadlines = tuple(
            execution.deadline_monotonic
            for execution in active.values()
            if not execution.timed_out and execution.deadline_monotonic is not None
        )
        deadline_wait = max(0.0, min(deadlines) - monotonic()) if deadlines else None
        if cancellation_poll_seconds is None:
            return deadline_wait
        if deadline_wait is None:
            return cancellation_poll_seconds
        return min(deadline_wait, cancellation_poll_seconds)

    def _expire_due_timeouts(
        self,
        *,
        run: WorkflowRun,
        graph: DependencyGraph,
        plan_task_ids: tuple[TaskId, ...],
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        task_definitions: Mapping[TaskId, TaskDefinition],
        active: Mapping[str, _ActiveExecution],
        pending_retries: dict[TaskId, _PendingRetry],
        event_factory: RuntimeEventFactory,
        workflow_already_failed: bool,
    ) -> bool:
        now_monotonic = monotonic()
        terminal_failure = False

        for handle_id in sorted(active):
            execution = active[handle_id]
            if (
                execution.timed_out
                or execution.deadline_monotonic is None
                or execution.deadline_monotonic > now_monotonic
            ):
                continue

            task_definition = task_definitions[execution.task_id]
            timeout_seconds = task_definition.timeout_seconds
            if timeout_seconds is None:
                raise RuntimeInvariantError(
                    reason=f"task '{execution.task_id}' reached timeout without timeout_seconds"
                )

            if task_definition.timeout_mode is TimeoutMode.HARD:
                self._hard_terminator().terminate(execution.handle)

            execution.timed_out = True
            timeout_error = ExecutionTimeoutError(
                task_id=execution.task_id,
                handler_ref=task_definition.handler_ref,
                timeout_seconds=timeout_seconds,
                timeout_mode=task_definition.timeout_mode.value,
            )
            failed_at = self._clock.now()
            self._state_machine.fail_attempt(
                execution.attempt,
                at=failed_at,
                error_type=timeout_error.error_type,
                error_message=timeout_error.error_message,
                error_category=timeout_error.error_category,
            )

            decision = self._retry_engine.decide(
                policy=task_definition.retry_policy,
                attempt_number=execution.attempt.attempt_number,
                error=timeout_error,
            )

            if decision.should_retry and not workflow_already_failed and not terminal_failure:
                if decision.next_attempt_number is None:
                    raise RuntimeInvariantError(
                        reason="timeout retry decision is missing next_attempt_number"
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
                            "error_type": timeout_error.error_type,
                            "error_category": timeout_error.error_category,
                            "timeout_mode": task_definition.timeout_mode.value,
                            "timeout_seconds": timeout_seconds,
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
                continue

            if workflow_already_failed or terminal_failure:
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
                            "error_type": timeout_error.error_type,
                            "error_category": timeout_error.error_category,
                            "timeout_mode": task_definition.timeout_mode.value,
                            "timeout_seconds": timeout_seconds,
                        },
                    ),
                )
                continue

            self._persist_terminal_failure(
                run=run,
                task_run=execution.task_run,
                attempt=execution.attempt,
                graph=graph,
                plan_task_ids=plan_task_ids,
                task_runs_by_task_id=task_runs_by_task_id,
                event_factory=event_factory,
                error_type=timeout_error.error_type,
                error_category=timeout_error.error_category,
            )
            terminal_failure = True

        return terminal_failure

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
                raise RuntimeInvariantError(reason="successful completion is missing TaskResult")
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
                raise RuntimeInvariantError(reason="retry decision is missing next_attempt_number")
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

    def _finish_cancellation(
        self,
        *,
        run: WorkflowRun,
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        active: dict[str, _ActiveExecution],
        pending_retries: dict[TaskId, _PendingRetry],
        capacity: CapacityManager,
        event_factory: RuntimeEventFactory,
        cancellation: CancellationController,
    ) -> WorkflowRun:
        request = cancellation.request_details
        reason = request.reason if request is not None else "requested"
        cancelled_task_runs: list[TaskRun] = []
        active_task_ids = {
            execution.task_id for execution in active.values() if not execution.timed_out
        }

        for task_run in task_runs_by_task_id.values():
            should_cancel = task_run.status in {
                TaskRunStatus.PENDING,
                TaskRunStatus.READY,
            } or (
                task_run.status is TaskRunStatus.RUNNING
                and task_run.task_id in pending_retries
                and task_run.task_id not in active_task_ids
            )
            if not should_cancel:
                continue
            self._state_machine.cancel_task(task_run, at=self._clock.now())
            cancelled_task_runs.append(task_run)

        pending_retries.clear()
        self._persist_cancelled_task_runs(cancelled_task_runs)

        hard_cancelled_handle_ids: set[str] = set()
        if self._concurrent_executor.capabilities.cancellation is CancellationCapability.HARD:
            terminator = self._hard_terminator()
            for execution in tuple(active.values()):
                terminated = terminator.terminate(execution.handle)
                if terminated and not execution.timed_out:
                    hard_cancelled_handle_ids.add(execution.handle.handle_id)

        log_runtime(
            logger,
            logging.INFO,
            "Workflow cancellation requested",
            context=LogContext(
                run_id=str(run.run_id),
                workflow_id=str(run.workflow_id),
            ),
            fields={
                "reason": reason,
                "cancelled_undispatched_tasks": len(cancelled_task_runs),
                "running_attempts": len(active),
            },
        )

        while active:
            completion = self._concurrent_executor.completion_queue.get()
            execution = active.get(completion.handle.handle_id)
            if execution is None:
                raise RuntimeInvariantError(
                    reason=(
                        "received completion for an execution handle "
                        f"not owned by cancelling run: '{completion.handle.handle_id}'"
                    )
                )
            del active[completion.handle.handle_id]
            capacity.release(execution.lease)
            if execution.timed_out:
                continue
            if execution.handle.handle_id in hard_cancelled_handle_ids:
                self._apply_hard_cancellation_completion(
                    execution=execution,
                    completion=completion,
                )
            else:
                self._apply_cancellation_completion(
                    execution=execution,
                    completion=completion,
                    event_factory=event_factory,
                )

        unexpected_running = tuple(
            task_run.task_id
            for task_run in task_runs_by_task_id.values()
            if task_run.status is TaskRunStatus.RUNNING
        )
        if unexpected_running:
            rendered = ", ".join(str(task_id) for task_id in unexpected_running)
            raise RuntimeInvariantError(
                reason=f"cancellation drained workers but RUNNING tasks remain: {rendered}"
            )

        finished_at = self._clock.now()
        self._state_machine.cancel_workflow(run, at=finished_at)
        self._persist_workflow_transition(
            run=run,
            event=event_factory.create(
                event_type=RuntimeEventType.WORKFLOW_CANCELLED,
                occurred_at=finished_at,
                payload={
                    "reason": reason,
                    "cancelled_undispatched_tasks": len(cancelled_task_runs),
                },
            ),
        )
        return self._metadata_store.get_workflow_run(run.run_id)

    def _drain_terminal_workflow_attempts(
        self,
        *,
        active: dict[str, _ActiveExecution],
        capacity: CapacityManager,
        event_factory: RuntimeEventFactory,
    ) -> None:
        while active:
            completion = self._concurrent_executor.completion_queue.get()
            execution = active.get(completion.handle.handle_id)
            if execution is None:
                raise RuntimeInvariantError(
                    reason=(
                        "received completion for an execution handle "
                        f"not owned by terminal run: '{completion.handle.handle_id}'"
                    )
                )
            del active[completion.handle.handle_id]
            capacity.release(execution.lease)
            if not execution.timed_out:
                self._apply_cancellation_completion(
                    execution=execution,
                    completion=completion,
                    event_factory=event_factory,
                )

    def _hard_terminator(self) -> _HardTerminationExecutor:
        if not isinstance(self._concurrent_executor, _HardTerminationExecutor):
            raise RuntimeInvariantError(
                reason=(
                    f"executor '{self._concurrent_executor.key}' declares hard termination "
                    "semantics but does not implement terminate(handle)"
                )
            )
        return self._concurrent_executor

    def _apply_hard_cancellation_completion(
        self,
        *,
        execution: _ActiveExecution,
        completion: AttemptCompletion,
    ) -> None:
        if completion.handle != execution.handle:
            raise RuntimeInvariantError(
                reason="hard-cancellation completion handle does not match active execution"
            )
        cancelled_at = self._clock.now()
        self._state_machine.cancel_attempt(execution.attempt, at=cancelled_at)
        self._state_machine.cancel_task(execution.task_run, at=cancelled_at)
        with self._metadata_store.unit_of_work() as uow:
            uow.save_task_attempt(execution.attempt)
            uow.save_task_run(execution.task_run)
            uow.commit()

    def _persist_cancelled_task_runs(
        self,
        task_runs: list[TaskRun],
    ) -> None:
        if not task_runs:
            return
        with self._metadata_store.unit_of_work() as uow:
            for task_run in task_runs:
                uow.save_task_run(task_run)
            uow.commit()

    def _apply_cancellation_completion(
        self,
        *,
        execution: _ActiveExecution,
        completion: AttemptCompletion,
        event_factory: RuntimeEventFactory,
    ) -> None:
        if completion.handle != execution.handle:
            raise RuntimeInvariantError(
                reason="cancellation completion handle does not match active execution"
            )

        if completion.succeeded:
            if completion.result is None:
                raise RuntimeInvariantError(reason="successful completion is missing TaskResult")
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
            return

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
                    "during_cancellation": True,
                },
            ),
        )

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
