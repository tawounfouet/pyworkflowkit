"""Tests for M32 ProcessExecutor."""

from __future__ import annotations

import os
import threading
import time

import pytest

from pyworkflowkit.adapters.executors import process as process_module
from pyworkflowkit.adapters.executors.process import ProcessExecutor
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
    ExecutorSerializationError,
    ExecutorShutdownError,
    InvalidHandlerError,
    TaskExecutionError,
)
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    RunContext,
    TimeoutCapability,
)


def _return_pid() -> int:
    return os.getpid()


def _return_context(context: RunContext) -> dict[str, object]:
    return {
        "task_id": str(context.task_id),
        "attempt_number": context.attempt_number,
        "parameter": context.workflow_parameters["name"],
        "upstream": context.dependency_outputs[TaskId("upstream")],
    }


def _raise_runtime_error() -> None:
    raise RuntimeError("boom")


def _sleep_long() -> str:
    time.sleep(10)
    return "late"


def _return_unserializable() -> object:
    return threading.Lock()


def _task(name: str) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(name),
        handler_ref=f"handlers:{name}",
        executor_key="process",
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


def test_process_executor_declares_hard_process_capabilities() -> None:
    executor = ProcessExecutor(max_workers=3)
    try:
        capabilities = executor.capabilities

        assert capabilities.supports_parallelism is True
        assert capabilities.max_concurrency == 3
        assert capabilities.timeout is TimeoutCapability.HARD
        assert capabilities.cancellation is CancellationCapability.HARD
    finally:
        executor.shutdown()


def test_process_executor_preserves_explicit_completion_queue() -> None:
    completion_queue = CompletionQueue()
    executor = ProcessExecutor(max_workers=1, completion_queue=completion_queue)
    try:
        assert executor.completion_queue is completion_queue
    finally:
        executor.shutdown()


def test_execute_runs_handler_in_an_isolated_process() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        result = executor.execute(
            task=_task("pid"),
            handler=_return_pid,
            context=_context("pid"),
        )

        assert isinstance(result.output, int)
        assert result.output != os.getpid()
    finally:
        executor.shutdown()


def test_run_context_crosses_explicit_process_transport_boundary() -> None:
    executor = ProcessExecutor(max_workers=1)
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


def test_task_failure_is_transferred_as_task_execution_error() -> None:
    executor = ProcessExecutor(max_workers=1)
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


def test_unpicklable_handler_is_rejected_before_process_start() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        with pytest.raises(ExecutorSerializationError) as exc_info:
            executor.submit(
                task=_task("lambda"),
                handler=lambda: "not portable",
                context=_context("lambda"),
            )

        assert exc_info.value.object_name == "handler"
        assert executor.active_handles() == ()
    finally:
        executor.shutdown()


def test_unpicklable_result_is_reported_as_serialization_error() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        with pytest.raises(ExecutorSerializationError) as exc_info:
            executor.execute(
                task=_task("result"),
                handler=_return_unserializable,
                context=_context("result"),
            )

        assert exc_info.value.object_name == "task result"
    finally:
        executor.shutdown()


def test_submit_publishes_completion_for_process_result() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        handle = executor.submit(
            task=_task("async"),
            handler=_return_pid,
            context=_context("async"),
        )
        completion = executor.completion_queue.get(timeout=5.0)

        assert completion.handle == handle
        assert completion.succeeded is True
        assert completion.result is not None
        assert completion.result.output != os.getpid()
        assert executor.wait(handle, timeout=1.0) is True
    finally:
        executor.shutdown()


def test_terminate_hard_stops_active_process() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        handle = executor.submit(
            task=_task("slow"),
            handler=_sleep_long,
            context=_context("slow"),
        )

        assert executor.terminate(handle) is True
        completion = executor.completion_queue.get(timeout=5.0)

        assert completion.handle == handle
        assert completion.succeeded is False
        assert executor.wait(handle, timeout=1.0) is True
    finally:
        executor.shutdown(wait=False)


def test_duplicate_attempt_submission_is_rejected() -> None:
    executor = ProcessExecutor(max_workers=1)
    task = _task("once")
    context = _context("once")
    handle = executor.submit(task=task, handler=_sleep_long, context=context)
    try:
        with pytest.raises(DuplicateExecutionSubmissionError):
            executor.submit(task=task, handler=_sleep_long, context=context)
    finally:
        executor.terminate(handle)
        executor.shutdown(wait=False)


def test_wait_rejects_unknown_handle() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        with pytest.raises(ExecutionHandleNotFoundError):
            executor.wait(
                ExecutionHandle(
                    handle_id="process:missing",
                    attempt_id=TaskAttemptId("missing"),
                    executor_key="process",
                )
            )
    finally:
        executor.shutdown()


def test_shutdown_rejects_new_submissions() -> None:
    executor = ProcessExecutor(max_workers=1)
    executor.shutdown()

    with pytest.raises(ExecutorShutdownError):
        executor.submit(
            task=_task("late"),
            handler=_return_pid,
            context=_context("late"),
        )


class _CapturingConnection:
    def __init__(self) -> None:
        self.messages: list[object] = []
        self.closed = False

    def send(self, value: object) -> None:
        self.messages.append(value)

    def close(self) -> None:
        self.closed = True


def test_worker_transport_success_path_is_unit_qualified() -> None:
    connection = _CapturingConnection()
    task = _task("worker-success")
    context = _context("worker-success")

    process_module._worker_main(
        connection,  # type: ignore[arg-type]
        process_module._task_snapshot(task),
        _return_pid,
        process_module._context_snapshot(context),
    )

    assert connection.closed is True
    assert len(connection.messages) == 1
    message = connection.messages[0]
    assert isinstance(message, process_module._WorkerMessage)
    assert message.result is not None
    assert message.error is None


def test_worker_transport_task_failure_path_is_unit_qualified() -> None:
    connection = _CapturingConnection()
    task = _task("worker-failure")
    context = _context("worker-failure")

    process_module._worker_main(
        connection,  # type: ignore[arg-type]
        process_module._task_snapshot(task),
        _raise_runtime_error,
        process_module._context_snapshot(context),
    )

    message = connection.messages[0]
    assert isinstance(message, process_module._WorkerMessage)
    assert message.result is None
    assert message.error is not None
    assert message.error.kind == "task"
    assert message.error.error_type == "RuntimeError"


def test_worker_transport_result_serialization_path_is_unit_qualified() -> None:
    connection = _CapturingConnection()
    task = _task("worker-serialization")
    context = _context("worker-serialization")

    process_module._worker_main(
        connection,  # type: ignore[arg-type]
        process_module._task_snapshot(task),
        _return_unserializable,
        process_module._context_snapshot(context),
    )

    message = connection.messages[0]
    assert isinstance(message, process_module._WorkerMessage)
    assert message.result is None
    assert message.error is not None
    assert message.error.kind == "serialization"


@pytest.mark.parametrize("max_workers", [True, 1.5, "2"])
def test_process_executor_rejects_non_integer_worker_counts(max_workers: object) -> None:
    with pytest.raises(TypeError):
        ProcessExecutor(max_workers=max_workers)  # type: ignore[arg-type]


def test_process_executor_rejects_non_positive_worker_count() -> None:
    with pytest.raises(ValueError):
        ProcessExecutor(max_workers=0)


def test_process_executor_rejects_unknown_start_method() -> None:
    with pytest.raises(ValueError):
        ProcessExecutor(start_method="not-a-real-start-method")


@pytest.mark.parametrize("terminate_grace_seconds", [True, "0.2"])
def test_process_executor_rejects_non_numeric_termination_grace(
    terminate_grace_seconds: object,
) -> None:
    with pytest.raises(TypeError):
        ProcessExecutor(
            terminate_grace_seconds=terminate_grace_seconds,  # type: ignore[arg-type]
        )


def test_process_executor_rejects_negative_termination_grace() -> None:
    with pytest.raises(ValueError):
        ProcessExecutor(terminate_grace_seconds=-0.1)


def test_process_executor_rejects_task_for_another_executor() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        task = TaskDefinition(
            task_id=TaskId("wrong-executor"),
            handler_ref="handlers:wrong",
            executor_key="thread",
        )
        with pytest.raises(InvalidHandlerError, match="executor key is 'process'"):
            executor.submit(
                task=task,
                handler=_return_pid,
                context=_context("wrong-executor"),
            )
    finally:
        executor.shutdown()
