"""Tests for M30 workflow cancellation coordination."""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.application.cancellation import CancellationController
from pyworkflowkit.application.completion import AttemptCompletion, CompletionQueue
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    BackoffStrategy,
    RuntimeEventType,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import (
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import WorkflowRun
from pyworkflowkit.domain.values import RetryPolicy

NOW = datetime(2026, 9, 26, 14, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class NoopSleeper:
    def sleep(self, seconds: float) -> None:
        del seconds


class DeterministicIdFactory:
    def new_workflow_run_id(self) -> WorkflowRunId:
        return WorkflowRunId("workflow-run-cancel")

    def new_task_run_id(
        self,
        *,
        run_id: WorkflowRunId,
        task_id: TaskId,
    ) -> TaskRunId:
        return TaskRunId(f"{run_id}:{task_id}")

    def new_task_attempt_id(
        self,
        *,
        task_run_id: TaskRunId,
        attempt_number: int,
    ) -> TaskAttemptId:
        return TaskAttemptId(f"{task_run_id}:attempt-{attempt_number}")

    def new_runtime_event_id(
        self,
        *,
        run_id: WorkflowRunId,
        event_sequence: int,
    ) -> RuntimeEventId:
        return RuntimeEventId(f"{run_id}:event-{event_sequence}")


class InterruptingCompletionQueue(CompletionQueue):
    def __init__(self) -> None:
        super().__init__()
        self._interrupt_once = True

    def get(self, *, timeout: float | None = None) -> AttemptCompletion:
        if self._interrupt_once:
            self._interrupt_once = False
            raise KeyboardInterrupt
        return super().get(timeout=timeout)


def _task(name: str) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(name),
        handler_ref=f"handlers:{name}",
        executor_key="thread",
    )


def _workflow(*names: str) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("cancel.workflow"),
        version="1",
        tasks=tuple(_task(name) for name in names),
    )


def _runtime(
    handlers: dict[str, object],
    *,
    max_workers: int = 1,
    completion_queue: CompletionQueue | None = None,
) -> tuple[ConcurrentRunner, MemoryMetadataStore, ThreadExecutor]:
    store = MemoryMetadataStore()
    registry = HandlerRegistry()
    for handler_ref, handler in handlers.items():
        registry.register(handler_ref, handler)  # type: ignore[arg-type]

    executor = ThreadExecutor(
        max_workers=max_workers,
        completion_queue=completion_queue,
    )
    runner = ConcurrentRunner(
        metadata_store=store,
        handler_registry=registry,
        executor=executor,
        clock=FixedClock(),
        id_factory=DeterministicIdFactory(),
        sleeper=NoopSleeper(),
        global_limit=max_workers,
    )
    return runner, store, executor


def test_cancellation_controller_preserves_first_request_reason() -> None:
    cancellation = CancellationController()

    assert cancellation.request(reason="user_requested") is True
    assert cancellation.request(reason="later_reason") is False
    assert cancellation.is_requested is True
    assert cancellation.request_details is not None
    assert cancellation.request_details.reason == "user_requested"


def test_pre_requested_cancellation_cancels_all_undispatched_tasks() -> None:
    workflow = _workflow("A", "B")
    cancellation = CancellationController()
    cancellation.request(reason="preflight")
    runner, store, executor = _runtime(
        {
            "handlers:A": lambda: "A",
            "handlers:B": lambda: "B",
        }
    )

    try:
        run = runner.run(workflow, cancellation=cancellation)
    finally:
        executor.shutdown()

    task_runs = store.list_task_runs(run.run_id)
    assert run.status is WorkflowRunStatus.CANCELLED
    assert {task.status for task in task_runs} == {TaskRunStatus.CANCELLED}
    assert all(not store.list_task_attempts(task.task_run_id) for task in task_runs)

    cancelled = [
        event
        for event in store.list_events(run.run_id)
        if event.event_type is RuntimeEventType.WORKFLOW_CANCELLED
    ]
    assert len(cancelled) == 1
    assert cancelled[0].payload["reason"] == "preflight"


def test_external_cancellation_stops_dispatch_and_allows_running_attempt_to_finish() -> None:
    started = threading.Event()
    release = threading.Event()
    cancellation = CancellationController()

    def running() -> str:
        started.set()
        release.wait(timeout=2.0)
        return "finished"

    workflow = _workflow("A", "B")
    runner, store, executor = _runtime(
        {
            "handlers:A": running,
            "handlers:B": lambda: "must-not-run",
        },
        max_workers=1,
    )
    result: list[WorkflowRun] = []

    thread = threading.Thread(
        target=lambda: result.append(runner.run(workflow, cancellation=cancellation))
    )
    thread.start()
    assert started.wait(timeout=2.0) is True

    assert cancellation.request(reason="user_requested") is True
    release.set()
    thread.join(timeout=3.0)

    try:
        assert thread.is_alive() is False
        run = result[0]
        task_runs = {task.task_id: task for task in store.list_task_runs(run.run_id)}

        assert run.status is WorkflowRunStatus.CANCELLED
        assert task_runs[TaskId("A")].status is TaskRunStatus.SUCCEEDED
        assert task_runs[TaskId("B")].status is TaskRunStatus.CANCELLED
        assert len(store.list_task_attempts(task_runs[TaskId("A")].task_run_id)) == 1
        assert not store.list_task_attempts(task_runs[TaskId("B")].task_run_id)
    finally:
        release.set()
        executor.shutdown()


def test_cancellation_suppresses_retry_after_running_attempt_failure() -> None:
    cancellation = CancellationController()
    calls = 0

    def failing() -> None:
        nonlocal calls
        calls += 1
        cancellation.request(reason="cancel-before-failure")
        raise RuntimeError("boom")

    task = TaskDefinition(
        task_id=TaskId("A"),
        handler_ref="handlers:A",
        executor_key="thread",
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_strategy=BackoffStrategy.FIXED,
            delay_seconds=0.1,
            retryable_error_categories=frozenset({"RuntimeError"}),
        ),
    )
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("cancel.retry"),
        version="1",
        tasks=(task,),
    )
    runner, store, executor = _runtime({"handlers:A": failing})

    try:
        run = runner.run(workflow, cancellation=cancellation)
    finally:
        executor.shutdown()

    task_run = store.list_task_runs(run.run_id)[0]
    attempts = store.list_task_attempts(task_run.task_run_id)

    assert run.status is WorkflowRunStatus.CANCELLED
    assert task_run.status is TaskRunStatus.FAILED
    assert calls == 1
    assert len(attempts) == 1
    assert attempts[0].status is TaskAttemptStatus.FAILED


def test_keyboard_interrupt_is_normalized_to_graceful_cancellation() -> None:
    queue = InterruptingCompletionQueue()
    workflow = _workflow("A")
    runner, store, executor = _runtime(
        {"handlers:A": lambda: "done"},
        completion_queue=queue,
    )

    try:
        run = runner.run(workflow)
    finally:
        executor.shutdown()

    task_run = store.list_task_runs(run.run_id)[0]
    cancelled = [
        event
        for event in store.list_events(run.run_id)
        if event.event_type is RuntimeEventType.WORKFLOW_CANCELLED
    ]

    assert run.status is WorkflowRunStatus.CANCELLED
    assert task_run.status is TaskRunStatus.SUCCEEDED
    assert len(cancelled) == 1
    assert cancelled[0].payload["reason"] == "keyboard_interrupt"
