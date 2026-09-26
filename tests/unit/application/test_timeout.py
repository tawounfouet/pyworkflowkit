"""Tests for M31 timeout semantics."""

from __future__ import annotations

import threading

import pytest

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    BackoffStrategy,
    TaskAttemptStatus,
    TaskRunStatus,
    TimeoutMode,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import TaskId, WorkflowId
from pyworkflowkit.domain.values import RetryPolicy
from pyworkflowkit.errors import TimeoutCapabilityError
from pyworkflowkit.ports.executor import RunContext


def _workflow(task: TaskDefinition) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("timeout.workflow"),
        version="1",
        tasks=(task,),
    )


def _thread_runner(
    task: TaskDefinition,
    handler: object,
) -> tuple[ConcurrentRunner, MemoryMetadataStore, ThreadExecutor]:
    store = MemoryMetadataStore()
    registry = HandlerRegistry()
    assert task.handler_ref is not None
    registry.register(task.handler_ref, handler)  # type: ignore[arg-type]
    executor = ThreadExecutor(max_workers=1)
    runner = ConcurrentRunner(
        metadata_store=store,
        handler_registry=registry,
        executor=executor,
        clock=SystemClock(),
        id_factory=UuidRuntimeIdFactory(),
        sleeper=SystemSleeper(),
        global_limit=1,
    )
    return runner, store, executor


def test_local_executor_rejects_soft_timeout_before_run_creation() -> None:
    task = TaskDefinition(
        task_id=TaskId("A"),
        handler_ref="handlers:A",
        executor_key="local",
        timeout_seconds=0.1,
    )
    workflow = _workflow(task)
    registry = HandlerRegistry()
    registry.register("handlers:A", lambda: "done")
    store = MemoryMetadataStore()
    runner = Runner(
        metadata_store=store,
        handler_registry=registry,
        executor=LocalExecutor(),
        clock=SystemClock(),
        id_factory=UuidRuntimeIdFactory(),
        sleeper=SystemSleeper(),
    )

    with pytest.raises(TimeoutCapabilityError, match="SOFT"):
        runner.run(workflow)


def test_thread_executor_rejects_hard_timeout_before_run_creation() -> None:
    task = TaskDefinition(
        task_id=TaskId("A"),
        handler_ref="handlers:A",
        executor_key="thread",
        timeout_seconds=0.1,
        timeout_mode=TimeoutMode.HARD,
    )
    workflow = _workflow(task)
    runner, store, executor = _thread_runner(task, lambda: "done")

    try:
        with pytest.raises(TimeoutCapabilityError, match="HARD"):
            runner.run(workflow)
    finally:
        executor.shutdown()


def test_soft_timeout_fails_attempt_and_workflow_but_late_completion_is_ignored() -> None:
    task = TaskDefinition(
        task_id=TaskId("A"),
        handler_ref="handlers:A",
        executor_key="thread",
        timeout_seconds=0.01,
        timeout_mode=TimeoutMode.SOFT,
    )

    def slow() -> str:
        threading.Event().wait(0.05)
        return "late-success"

    workflow = _workflow(task)
    runner, store, executor = _thread_runner(task, slow)

    try:
        run = runner.run(workflow)
    finally:
        executor.shutdown()

    task_run = store.list_task_runs(run.run_id)[0]
    attempts = store.list_task_attempts(task_run.task_run_id)

    assert run.status is WorkflowRunStatus.FAILED
    assert task_run.status is TaskRunStatus.FAILED
    assert len(attempts) == 1
    assert attempts[0].status is TaskAttemptStatus.FAILED
    assert attempts[0].error_type == "ExecutionTimeoutError"
    assert attempts[0].error_category == "timeout"


def test_soft_timeout_routes_through_retry_engine_and_second_attempt_can_succeed() -> None:
    task = TaskDefinition(
        task_id=TaskId("A"),
        handler_ref="handlers:A",
        executor_key="thread",
        timeout_seconds=0.01,
        timeout_mode=TimeoutMode.SOFT,
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_strategy=BackoffStrategy.NONE,
            retryable_error_categories=frozenset({"timeout"}),
        ),
    )

    def unstable(context: RunContext) -> str:
        if context.attempt_number == 1:
            threading.Event().wait(0.05)
            return "late-first-attempt"
        return "second-attempt"

    workflow = _workflow(task)
    runner, store, executor = _thread_runner(task, unstable)

    try:
        run = runner.run(workflow)
    finally:
        executor.shutdown()

    task_run = store.list_task_runs(run.run_id)[0]
    attempts = store.list_task_attempts(task_run.task_run_id)

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert task_run.status is TaskRunStatus.SUCCEEDED
    assert [attempt.status for attempt in attempts] == [
        TaskAttemptStatus.FAILED,
        TaskAttemptStatus.SUCCEEDED,
    ]
    assert attempts[0].error_type == "ExecutionTimeoutError"
    assert attempts[0].error_category == "timeout"
