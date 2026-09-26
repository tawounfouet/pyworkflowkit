"""Tests for M33 AsyncExecutor."""

from __future__ import annotations

import asyncio
import threading

import pytest

from pyworkflowkit.adapters.executors.asyncio import AsyncExecutor
from pyworkflowkit.application.completion import CompletionQueue, ExecutionHandle
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
    ExecutorWorkerError,
    InvalidHandlerError,
    TaskExecutionError,
)
from pyworkflowkit.ports.executor import AsyncExecutor as AsyncExecutorPort
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    RunContext,
    TimeoutCapability,
)


async def _return_value() -> str:
    await asyncio.sleep(0)
    return "ok"


async def _return_context(context: RunContext) -> dict[str, object]:
    await asyncio.sleep(0)
    return {
        "task_id": str(context.task_id),
        "attempt_number": context.attempt_number,
        "parameter": context.workflow_parameters["name"],
        "upstream": context.dependency_outputs[TaskId("upstream")],
    }


async def _raise_runtime_error() -> None:
    await asyncio.sleep(0)
    raise RuntimeError("boom")


def _sync_handler() -> str:
    return "sync"


def _task(name: str) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(name),
        handler_ref=f"handlers:{name}",
        executor_key="async",
    )


def _context(name: str) -> RunContext:
    return RunContext(
        workflow_run_id=WorkflowRunId("run"),
        task_run_id=TaskRunId(f"task-run-{name}"),
        attempt_id=TaskAttemptId(f"attempt-{name}"),
        task_id=TaskId(name),
        attempt_number=1,
        workflow_parameters={"name": "demo"},
        dependency_outputs={TaskId("upstream"): {"rows": 3}},
    )


def test_async_executor_declares_native_async_capabilities() -> None:
    executor = AsyncExecutor(max_concurrency=8)
    try:
        capabilities = executor.capabilities

        assert capabilities.supports_parallelism is True
        assert capabilities.supports_async is True
        assert capabilities.max_concurrency == 8
        assert capabilities.timeout is TimeoutCapability.SOFT
        assert capabilities.cancellation is CancellationCapability.COOPERATIVE
        assert isinstance(executor, AsyncExecutorPort)
    finally:
        executor.shutdown()


def test_async_executor_preserves_explicit_completion_queue() -> None:
    completion_queue = CompletionQueue()
    executor = AsyncExecutor(max_concurrency=1, completion_queue=completion_queue)
    try:
        assert executor.completion_queue is completion_queue
    finally:
        executor.shutdown()


def test_execute_async_natively_awaits_handler() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    try:
        result = asyncio.run(
            executor.execute_async(
                task=_task("native"),
                handler=_return_value,
                context=_context("native"),
            )
        )

        assert result.output == "ok"
    finally:
        executor.shutdown()


def test_execute_sync_bridge_runs_async_handler_on_executor_loop() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    try:
        result = executor.execute(
            task=_task("bridge"),
            handler=_return_value,
            context=_context("bridge"),
        )

        assert result.output == "ok"
    finally:
        executor.shutdown()


def test_async_context_is_propagated_without_serialization_boundary() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    try:
        result = executor.execute(
            task=_task("context"),
            handler=_return_context,
            context=_context("context"),
        )

        assert result.output == {
            "task_id": "context",
            "attempt_number": 1,
            "parameter": "demo",
            "upstream": {"rows": 3},
        }
    finally:
        executor.shutdown()


def test_sync_handler_is_rejected_by_async_executor_contract() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    try:
        with pytest.raises(InvalidHandlerError, match="awaitable"):
            executor.execute(
                task=_task("sync"),
                handler=_sync_handler,
                context=_context("sync"),
            )
    finally:
        executor.shutdown()


def test_async_handler_failure_is_normalized() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    try:
        with pytest.raises(TaskExecutionError) as exc_info:
            executor.execute(
                task=_task("broken"),
                handler=_raise_runtime_error,
                context=_context("broken"),
            )

        assert exc_info.value.error_type == "RuntimeError"
        assert exc_info.value.error_message == "boom"
    finally:
        executor.shutdown()


def test_submit_publishes_async_completion() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    try:
        handle = executor.submit(
            task=_task("submit"),
            handler=_return_value,
            context=_context("submit"),
        )
        completion = executor.completion_queue.get(timeout=2.0)

        assert completion.handle == handle
        assert completion.succeeded is True
        assert completion.result is not None
        assert completion.result.output == "ok"
        assert executor.wait(handle, timeout=1.0) is True
        assert executor.active_handles() == ()
    finally:
        executor.shutdown()


def test_cancel_cooperatively_cancels_running_async_task() -> None:
    started = threading.Event()

    async def slow() -> str:
        started.set()
        await asyncio.sleep(10)
        return "late"

    executor = AsyncExecutor(max_concurrency=1)
    try:
        handle = executor.submit(
            task=_task("cancel"),
            handler=slow,
            context=_context("cancel"),
        )
        assert started.wait(timeout=2.0)

        assert executor.cancel(handle) is True
        completion = executor.completion_queue.get(timeout=2.0)

        assert completion.handle == handle
        assert completion.succeeded is False
        assert isinstance(completion.error, ExecutorWorkerError)
        assert completion.error.error_type == "CancelledError"
        assert executor.wait(handle, timeout=1.0) is True
    finally:
        executor.shutdown(wait=False)
        executor.shutdown(wait=True)


def test_capacity_rejects_submission_beyond_declared_limit() -> None:
    started = threading.Event()

    async def slow() -> str:
        started.set()
        await asyncio.sleep(10)
        return "late"

    executor = AsyncExecutor(max_concurrency=1)
    first = executor.submit(
        task=_task("first"),
        handler=slow,
        context=_context("first"),
    )
    try:
        assert started.wait(timeout=2.0)

        with pytest.raises(ExecutorWorkerError, match="AsyncCapacityExceeded"):
            executor.submit(
                task=_task("second"),
                handler=_return_value,
                context=_context("second"),
            )
    finally:
        executor.cancel(first)
        executor.completion_queue.get(timeout=2.0)
        executor.shutdown()


def test_duplicate_attempt_submission_is_rejected() -> None:
    started = threading.Event()

    async def slow() -> str:
        started.set()
        await asyncio.sleep(10)
        return "late"

    executor = AsyncExecutor(max_concurrency=2)
    task = _task("once")
    context = _context("once")
    first = executor.submit(task=task, handler=slow, context=context)
    try:
        assert started.wait(timeout=2.0)
        with pytest.raises(DuplicateExecutionSubmissionError):
            executor.submit(task=task, handler=slow, context=context)
    finally:
        executor.cancel(first)
        executor.completion_queue.get(timeout=2.0)
        executor.shutdown()


def test_wait_and_cancel_reject_unknown_handle() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    unknown = ExecutionHandle(
        handle_id="async:missing",
        attempt_id=TaskAttemptId("missing"),
        executor_key="async",
    )
    try:
        with pytest.raises(ExecutionHandleNotFoundError):
            executor.wait(unknown)
        with pytest.raises(ExecutionHandleNotFoundError):
            executor.cancel(unknown)
    finally:
        executor.shutdown()


def test_wait_rejects_negative_timeout() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    handle = executor.submit(
        task=_task("wait"),
        handler=_return_value,
        context=_context("wait"),
    )
    try:
        with pytest.raises(ValueError, match="timeout"):
            executor.wait(handle, timeout=-1)
        executor.completion_queue.get(timeout=2.0)
    finally:
        executor.shutdown()


def test_shutdown_rejects_new_submissions() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    executor.shutdown()

    with pytest.raises(ExecutorShutdownError):
        executor.submit(
            task=_task("late"),
            handler=_return_value,
            context=_context("late"),
        )


@pytest.mark.parametrize("max_concurrency", [True, 1.5, "2"])
def test_async_executor_rejects_non_integer_capacity(max_concurrency: object) -> None:
    with pytest.raises(TypeError):
        AsyncExecutor(max_concurrency=max_concurrency)  # type: ignore[arg-type]


def test_async_executor_rejects_non_positive_capacity() -> None:
    with pytest.raises(ValueError):
        AsyncExecutor(max_concurrency=0)


def test_async_executor_rejects_blank_loop_thread_name() -> None:
    with pytest.raises(ValueError):
        AsyncExecutor(loop_thread_name=" ")
