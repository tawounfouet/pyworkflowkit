"""Tests for M27 execution completion primitives."""

import threading

import pytest

from pyworkflowkit.application.completion import (
    AttemptCompletion,
    CompletionQueue,
    ExecutionHandle,
)
from pyworkflowkit.domain.ids import TaskAttemptId, TaskId
from pyworkflowkit.domain.values import TaskResult
from pyworkflowkit.errors import TaskExecutionError


def _handle(name: str = "handle-1") -> ExecutionHandle:
    return ExecutionHandle(
        handle_id=name,
        attempt_id=TaskAttemptId(f"attempt-{name}"),
        executor_key="thread",
    )


def test_execution_handle_validates_identity() -> None:
    with pytest.raises(ValueError, match="handle_id"):
        ExecutionHandle(
            handle_id="",
            attempt_id=TaskAttemptId("attempt-1"),
            executor_key="thread",
        )


def test_attempt_completion_requires_exactly_one_terminal_outcome() -> None:
    handle = _handle()

    with pytest.raises(ValueError, match="exactly one"):
        AttemptCompletion(handle=handle)

    with pytest.raises(ValueError, match="exactly one"):
        AttemptCompletion(
            handle=handle,
            result=TaskResult(output="ok"),
            error=TaskExecutionError(
                task_id=TaskId("task"),
                handler_ref="handlers:task",
                error_type="RuntimeError",
                error_message="boom",
            ),
        )


def test_success_completion_exposes_result() -> None:
    completion = AttemptCompletion(
        handle=_handle(),
        result=TaskResult(output={"rows": 2}),
    )

    assert completion.succeeded is True
    assert completion.result is not None
    assert completion.result.output == {"rows": 2}
    assert completion.error is None


def test_failure_completion_exposes_executor_error() -> None:
    error = TaskExecutionError(
        task_id=TaskId("task"),
        handler_ref="handlers:task",
        error_type="RuntimeError",
        error_message="boom",
    )
    completion = AttemptCompletion(handle=_handle(), error=error)

    assert completion.succeeded is False
    assert completion.error is error
    assert completion.result is None


def test_completion_queue_is_fifo() -> None:
    queue = CompletionQueue()
    first = AttemptCompletion(
        handle=_handle("a"),
        result=TaskResult(output="a"),
    )
    second = AttemptCompletion(
        handle=_handle("b"),
        result=TaskResult(output="b"),
    )

    queue.put(first)
    queue.put(second)

    assert queue.get_nowait() is first
    assert queue.get_nowait() is second
    assert queue.get_nowait() is None


def test_completion_queue_drain_returns_all_available_completions() -> None:
    queue = CompletionQueue()
    queue.put(
        AttemptCompletion(
            handle=_handle("a"),
            result=TaskResult(output="a"),
        )
    )
    queue.put(
        AttemptCompletion(
            handle=_handle("b"),
            result=TaskResult(output="b"),
        )
    )

    drained = queue.drain()

    assert [completion.handle.handle_id for completion in drained] == ["a", "b"]
    assert queue.empty() is True


def test_completion_queue_transfers_from_worker_thread() -> None:
    queue = CompletionQueue()
    completion = AttemptCompletion(
        handle=_handle("worker"),
        result=TaskResult(output="done"),
    )

    thread = threading.Thread(target=queue.put, args=(completion,))
    thread.start()

    received = queue.get(timeout=1.0)
    thread.join()

    assert received is completion
    assert len(queue) == 0


def test_completion_queue_rejects_negative_timeout() -> None:
    with pytest.raises(ValueError, match="timeout"):
        CompletionQueue().get(timeout=-0.1)
