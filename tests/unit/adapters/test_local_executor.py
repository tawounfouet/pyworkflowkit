"""Tests for synchronous same-process LocalExecutor."""

import pytest

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.ids import (
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.domain.values import TaskResult
from pyworkflowkit.errors import InvalidHandlerError, TaskExecutionError
from pyworkflowkit.ports.executor import Executor, RunContext


def task(
    *,
    executor_key: str = "local",
    handler_ref: str | None = "tests:handler",
) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId("task"),
        executor_key=executor_key,
        handler_ref=handler_ref,
    )


def context() -> RunContext:
    return RunContext(
        workflow_run_id=WorkflowRunId("run-1"),
        task_run_id=TaskRunId("task-run-1"),
        attempt_id=TaskAttemptId("attempt-1"),
        task_id=TaskId("task"),
        attempt_number=1,
        workflow_parameters={"source": "input.csv"},
        dependency_outputs={TaskId("upstream"): 42},
    )


def test_local_executor_satisfies_executor_protocol() -> None:
    executor = LocalExecutor()

    assert isinstance(executor, Executor)
    assert executor.key == "local"
    assert executor.capabilities.supports_parallelism is False
    assert executor.capabilities.supports_hard_timeout is False
    assert executor.capabilities.supports_hard_cancellation is False


def test_local_executor_executes_zero_argument_handler() -> None:
    executor = LocalExecutor()

    result = executor.execute(
        task=task(),
        handler=lambda: "ok",
        context=context(),
    )

    assert result == TaskResult(output="ok")


def test_local_executor_executes_context_handler() -> None:
    executor = LocalExecutor()

    def handler(run_context: RunContext) -> object:
        return {
            "source": run_context.workflow_parameters["source"],
            "upstream": run_context.dependency_outputs[TaskId("upstream")],
        }

    result = executor.execute(
        task=task(),
        handler=handler,
        context=context(),
    )

    assert result.output == {
        "source": "input.csv",
        "upstream": 42,
    }


def test_local_executor_preserves_explicit_task_result() -> None:
    expected = TaskResult(output="ok", metadata={"rows": 10})

    result = LocalExecutor().execute(
        task=task(),
        handler=lambda: expected,
        context=context(),
    )

    assert result is expected


def test_local_executor_normalizes_none_to_empty_task_result() -> None:
    result = LocalExecutor().execute(
        task=task(),
        handler=lambda: None,
        context=context(),
    )

    assert result == TaskResult()


def test_local_executor_rejects_task_for_other_executor() -> None:
    with pytest.raises(InvalidHandlerError, match="remote"):
        LocalExecutor().execute(
            task=task(executor_key="remote"),
            handler=lambda: None,
            context=context(),
        )


def test_local_executor_rejects_handler_with_two_required_arguments() -> None:
    def invalid(first: object, second: object) -> None:
        del first, second

    with pytest.raises(InvalidHandlerError, match="zero arguments or one RunContext"):
        LocalExecutor().execute(
            task=task(),
            handler=invalid,  # type: ignore[arg-type]
            context=context(),
        )


def test_local_executor_rejects_variadic_handler() -> None:
    def invalid(*args: object) -> None:
        del args

    with pytest.raises(InvalidHandlerError):
        LocalExecutor().execute(
            task=task(),
            handler=invalid,  # type: ignore[arg-type]
            context=context(),
        )


def test_local_executor_wraps_handler_exception_and_preserves_cause() -> None:
    class HandlerFailure(RuntimeError):
        pass

    def failing_handler() -> None:
        raise HandlerFailure("boom")

    with pytest.raises(TaskExecutionError) as exc_info:
        LocalExecutor().execute(
            task=task(),
            handler=failing_handler,
            context=context(),
        )

    error = exc_info.value
    assert error.task_id == TaskId("task")
    assert error.handler_ref == "tests:handler"
    assert error.error_type == "HandlerFailure"
    assert error.error_message == "boom"
    assert error.error_category == "HandlerFailure"
    assert isinstance(error.__cause__, HandlerFailure)


def test_local_executor_does_not_wrap_keyboard_interrupt() -> None:
    def interrupted() -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        LocalExecutor().execute(
            task=task(),
            handler=interrupted,
            context=context(),
        )
