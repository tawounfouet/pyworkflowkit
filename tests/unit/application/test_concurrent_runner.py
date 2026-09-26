"""Tests for M29 ConcurrentRunner coordination semantics."""

from __future__ import annotations

import threading
from collections.abc import Mapping
from datetime import UTC, datetime

from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    BackoffStrategy,
    RuntimeEventType,
    SkipReason,
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
from pyworkflowkit.domain.values import RetryPolicy
from pyworkflowkit.ports.executor import RunContext

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class RecordingSleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.calls.append(seconds)


class DeterministicIdFactory:
    def new_workflow_run_id(self) -> WorkflowRunId:
        return WorkflowRunId("workflow-run-concurrent")

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


def _task(
    task_id: str,
    *depends_on: str,
    retry_policy: RetryPolicy | None = None,
) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(task_id),
        handler_ref=f"handlers:{task_id}",
        depends_on=tuple(TaskId(value) for value in depends_on),
        executor_key="thread",
        retry_policy=retry_policy or RetryPolicy(),
    )


def _workflow(*tasks: TaskDefinition) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("concurrent.workflow"),
        version="1",
        tasks=tasks,
    )


def _runtime(
    handlers: Mapping[str, object],
    *,
    max_workers: int = 4,
    global_limit: int | None = None,
    sleeper: RecordingSleeper | None = None,
) -> tuple[ConcurrentRunner, MemoryMetadataStore, ThreadExecutor]:
    store = MemoryMetadataStore()
    registry = HandlerRegistry()
    for handler_ref, handler in handlers.items():
        registry.register(handler_ref, handler)  # type: ignore[arg-type]

    executor = ThreadExecutor(max_workers=max_workers)
    runner = ConcurrentRunner(
        metadata_store=store,
        handler_registry=registry,
        executor=executor,
        clock=FixedClock(),
        id_factory=DeterministicIdFactory(),
        sleeper=sleeper or RecordingSleeper(),
        global_limit=global_limit,
    )
    return runner, store, executor


def test_fan_out_runs_ready_siblings_concurrently_and_fan_in_waits_for_both() -> None:
    sibling_barrier = threading.Barrier(2)
    seen: list[str] = []
    seen_lock = threading.Lock()

    def fetch() -> str:
        return "root"

    def sibling(context: RunContext) -> str:
        sibling_barrier.wait(timeout=2.0)
        with seen_lock:
            seen.append(str(context.task_id))
        return str(context.task_id)

    def join(context: RunContext) -> tuple[object, object]:
        return (
            context.dependency_outputs[TaskId("B")],
            context.dependency_outputs[TaskId("C")],
        )

    workflow = _workflow(
        _task("A"),
        _task("B", "A"),
        _task("C", "A"),
        _task("D", "B", "C"),
    )
    runner, store, executor = _runtime(
        {
            "handlers:A": fetch,
            "handlers:B": sibling,
            "handlers:C": sibling,
            "handlers:D": join,
        },
        max_workers=2,
    )
    try:
        run = runner.run(workflow)
    finally:
        executor.shutdown()

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert sorted(seen) == ["B", "C"]
    task_runs = {task.task_id: task for task in store.list_task_runs(run.run_id)}
    assert all(task.status is TaskRunStatus.SUCCEEDED for task in task_runs.values())
    d_attempts = store.list_task_attempts(task_runs[TaskId("D")].task_run_id)
    assert len(d_attempts) == 1


def test_capacity_bounds_parallel_handlers_even_when_executor_has_more_workers() -> None:
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    active = 0
    maximum = 0

    def bounded() -> str:
        nonlocal active, maximum
        with lock:
            active += 1
            maximum = max(maximum, active)
        barrier.wait(timeout=2.0)
        with lock:
            active -= 1
        return "done"

    workflow = _workflow(*(_task(name) for name in ("A", "B", "C", "D")))
    runner, _, executor = _runtime(
        {f"handlers:{name}": bounded for name in ("A", "B", "C", "D")},
        max_workers=4,
        global_limit=2,
    )
    try:
        run = runner.run(workflow)
    finally:
        executor.shutdown()

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert maximum == 2


def test_duplicate_ready_race_does_not_dispatch_join_task_twice() -> None:
    barrier = threading.Barrier(2)

    def sibling() -> str:
        barrier.wait(timeout=2.0)
        return "ok"

    workflow = _workflow(
        _task("A"),
        _task("B", "A"),
        _task("C", "A"),
        _task("D", "B", "C"),
    )
    runner, store, executor = _runtime(
        {
            "handlers:A": lambda: "A",
            "handlers:B": sibling,
            "handlers:C": sibling,
            "handlers:D": lambda: "D",
        },
        max_workers=2,
    )
    try:
        run = runner.run(workflow)
    finally:
        executor.shutdown()

    task_runs = {task.task_id: task for task in store.list_task_runs(run.run_id)}
    d_run = task_runs[TaskId("D")]
    assert len(store.list_task_attempts(d_run.task_run_id)) == 1
    d_ready_events = [
        event
        for event in store.list_events(run.run_id)
        if event.event_type is RuntimeEventType.TASK_READY
        and event.task_id == TaskId("D")
    ]
    assert len(d_ready_events) == 1


def test_fail_fast_allows_already_running_sibling_to_finish_and_skips_downstream() -> None:
    barrier = threading.Barrier(2)
    failure_visible = threading.Event()

    def failing() -> None:
        barrier.wait(timeout=2.0)
        failure_visible.set()
        raise RuntimeError("boom")

    def running_sibling() -> str:
        barrier.wait(timeout=2.0)
        assert failure_visible.wait(timeout=2.0)
        return "sibling-finished"

    workflow = _workflow(
        _task("A"),
        _task("B", "A"),
        _task("C", "A"),
        _task("D", "B", "C"),
        _task("E"),
    )
    runner, store, executor = _runtime(
        {
            "handlers:A": lambda: "A",
            "handlers:B": failing,
            "handlers:C": running_sibling,
            "handlers:D": lambda: "never",
            "handlers:E": lambda: "independent",
        },
        max_workers=3,
        global_limit=3,
    )
    try:
        run = runner.run(workflow)
    finally:
        executor.shutdown()

    statuses = {task.task_id: task for task in store.list_task_runs(run.run_id)}
    assert run.status is WorkflowRunStatus.FAILED
    assert statuses[TaskId("B")].status is TaskRunStatus.FAILED
    assert statuses[TaskId("C")].status is TaskRunStatus.SUCCEEDED
    assert statuses[TaskId("D")].status is TaskRunStatus.SKIPPED
    assert statuses[TaskId("D")].skip_reason is SkipReason.DEPENDENCY_FAILED
    assert statuses[TaskId("E")].status in {
        TaskRunStatus.SUCCEEDED,
        TaskRunStatus.SKIPPED,
    }


def test_retry_creates_new_attempt_without_losing_concurrent_runner_authority() -> None:
    calls = 0
    sleeper = RecordingSleeper()

    def unstable() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary")
        return "ok"

    policy = RetryPolicy(
        max_attempts=2,
        backoff_strategy=BackoffStrategy.FIXED,
        delay_seconds=0.25,
        retryable_error_categories=frozenset({"RuntimeError"}),
    )
    workflow = _workflow(_task("A", retry_policy=policy))
    runner, store, executor = _runtime(
        {"handlers:A": unstable},
        max_workers=1,
        sleeper=sleeper,
    )
    try:
        run = runner.run(workflow)
    finally:
        executor.shutdown()

    task_run = store.list_task_runs(run.run_id)[0]
    attempts = store.list_task_attempts(task_run.task_run_id)

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert calls == 2
    assert sleeper.calls == [0.25]
    assert [attempt.status for attempt in attempts] == [
        TaskAttemptStatus.FAILED,
        TaskAttemptStatus.SUCCEEDED,
    ]


def test_two_running_siblings_can_fail_without_second_workflow_transition() -> None:
    barrier = threading.Barrier(2)

    def fail(name: str) -> object:
        def handler() -> None:
            barrier.wait(timeout=2.0)
            raise RuntimeError(name)

        return handler

    workflow = _workflow(_task("A"), _task("B"))
    runner, store, executor = _runtime(
        {
            "handlers:A": fail("A"),
            "handlers:B": fail("B"),
        },
        max_workers=2,
    )
    try:
        run = runner.run(workflow)
    finally:
        executor.shutdown()

    assert run.status is WorkflowRunStatus.FAILED
    assert {
        task.status for task in store.list_task_runs(run.run_id)
    } == {TaskRunStatus.FAILED}
    workflow_failed_events = [
        event
        for event in store.list_events(run.run_id)
        if event.event_type is RuntimeEventType.WORKFLOW_FAILED
    ]
    assert len(workflow_failed_events) == 1
