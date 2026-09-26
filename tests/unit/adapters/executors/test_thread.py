"""Tests for M28 ThreadExecutor."""

from __future__ import annotations

import threading

import pytest

from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.application.completion import ExecutionHandle
from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.ids import (
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.errors import (
    DuplicateExecutionSubmissionError,
    ExecutionHandleNotFoundError,
    ExecutorShutdownError,
    TaskExecutionError,
)
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    RunContext,
    TimeoutCapability,
)


def _task(name: str) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(name),
        handler_ref=f"handlers:{name}",
        executor_key="thread",
    )


def _context(name: str) -> RunContext:
    return RunContext(
        workflow_run_id=WorkflowRunId("run"),
        task_run_id=TaskRunId(f"task-run-{name}"),
        attempt_id=TaskAttemptId(f"attempt-{name}"),
        task_id=TaskId(name),
        attempt_number=1,
    )


def test_thread_executor_preserves_explicit_completion_queue() -> None:
    from pyworkflowkit.application.completion import CompletionQueue

    completion_queue = CompletionQueue()
    executor = ThreadExecutor(max_workers=1, completion_queue=completion_queue)
    try:
        assert executor.completion_queue is completion_queue
    finally:
        executor.shutdown()


def test_thread_executor_declares_parallel_soft_timeout_capabilities() -> None:
    executor = ThreadExecutor(max_workers=3)
    try:
        capabilities = executor.capabilities

        assert capabilities.supports_parallelism is True
        assert capabilities.max_concurrency == 3
        assert capabilities.timeout is TimeoutCapability.SOFT
        assert capabilities.cancellation is CancellationCapability.NONE
    finally:
        executor.shutdown()


def test_thread_executor_executes_two_handlers_concurrently() -> None:
    executor = ThreadExecutor(max_workers=2)
    entered = threading.Barrier(3)
    release = threading.Event()

    def handler() -> str:
        entered.wait(timeout=1.0)
        release.wait(timeout=1.0)
        return "ok"

    try:
        first = executor.submit(
            task=_task("a"),
            handler=handler,
            context=_context("a"),
        )
        second = executor.submit(
            task=_task("b"),
            handler=handler,
            context=_context("b"),
        )

        entered.wait(timeout=1.0)
        assert {handle.handle_id for handle in executor.active_handles()} == {
            first.handle_id,
            second.handle_id,
        }

        release.set()

        completions = {
            executor.completion_queue.get(timeout=1.0).handle.handle_id,
            executor.completion_queue.get(timeout=1.0).handle.handle_id,
        }
        assert completions == {first.handle_id, second.handle_id}
    finally:
        release.set()
        executor.shutdown()


def test_soft_wait_timeout_does_not_stop_running_workload() -> None:
    executor = ThreadExecutor(max_workers=1)
    entered = threading.Event()
    release = threading.Event()

    def handler() -> str:
        entered.set()
        release.wait(timeout=1.0)
        return "finished"

    try:
        handle = executor.submit(
            task=_task("slow"),
            handler=handler,
            context=_context("slow"),
        )
        assert entered.wait(timeout=1.0) is True

        assert executor.wait(handle, timeout=0) is False
        assert handle in executor.active_handles()

        release.set()

        assert executor.wait(handle, timeout=1.0) is True
        completion = executor.completion_queue.get(timeout=1.0)
        assert completion.handle == handle
        assert completion.succeeded is True
        assert completion.result is not None
        assert completion.result.output == "finished"
    finally:
        release.set()
        executor.shutdown()


def test_handler_failure_is_transferred_as_completion_error() -> None:
    executor = ThreadExecutor(max_workers=1)

    def handler() -> None:
        raise RuntimeError("boom")

    try:
        handle = executor.submit(
            task=_task("broken"),
            handler=handler,
            context=_context("broken"),
        )

        completion = executor.completion_queue.get(timeout=1.0)

        assert completion.handle == handle
        assert completion.succeeded is False
        assert isinstance(completion.error, TaskExecutionError)
        assert completion.error.error_message == "boom"
    finally:
        executor.shutdown()


def test_duplicate_attempt_submission_is_rejected() -> None:
    executor = ThreadExecutor(max_workers=1)
    release = threading.Event()

    def handler() -> str:
        release.wait(timeout=1.0)
        return "done"

    try:
        task = _task("once")
        context = _context("once")
        executor.submit(task=task, handler=handler, context=context)

        with pytest.raises(DuplicateExecutionSubmissionError):
            executor.submit(task=task, handler=handler, context=context)
    finally:
        release.set()
        executor.shutdown()


def test_wait_rejects_unknown_handle() -> None:
    executor = ThreadExecutor(max_workers=1)
    try:
        with pytest.raises(ExecutionHandleNotFoundError):
            executor.wait(
                ExecutionHandle(
                    handle_id="thread:missing",
                    attempt_id=TaskAttemptId("missing"),
                    executor_key="thread",
                )
            )
    finally:
        executor.shutdown()


def test_shutdown_rejects_new_submissions() -> None:
    executor = ThreadExecutor(max_workers=1)
    executor.shutdown()

    assert executor.is_shutdown is True

    with pytest.raises(ExecutorShutdownError):
        executor.submit(
            task=_task("late"),
            handler=lambda: "late",
            context=_context("late"),
        )
