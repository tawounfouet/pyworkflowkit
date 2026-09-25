"""Contract tests shared by the built-in LocalExecutor implementation."""

from collections.abc import Callable

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
from pyworkflowkit.errors import TaskExecutionError
from pyworkflowkit.ports.executor import Executor, RunContext


@pytest.fixture
def executor() -> Executor:
    return LocalExecutor()


@pytest.fixture
def definition() -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId("contract-task"),
        handler_ref="contract:handler",
    )


@pytest.fixture
def run_context() -> RunContext:
    return RunContext(
        workflow_run_id=WorkflowRunId("workflow-run"),
        task_run_id=TaskRunId("task-run"),
        attempt_id=TaskAttemptId("attempt"),
        task_id=TaskId("contract-task"),
        attempt_number=1,
    )


def test_executor_returns_task_result(
    executor: Executor,
    definition: TaskDefinition,
    run_context: RunContext,
) -> None:
    handler: Callable[[], object] = lambda: "result"

    result = executor.execute(
        task=definition,
        handler=handler,
        context=run_context,
    )

    assert result == TaskResult(output="result")


def test_executor_translates_ordinary_handler_failure(
    executor: Executor,
    definition: TaskDefinition,
    run_context: RunContext,
) -> None:
    def handler() -> object:
        raise ValueError("invalid input")

    with pytest.raises(TaskExecutionError) as exc_info:
        executor.execute(
            task=definition,
            handler=handler,
            context=run_context,
        )

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_executor_does_not_mutate_task_definition(
    executor: Executor,
    definition: TaskDefinition,
    run_context: RunContext,
) -> None:
    before = definition

    executor.execute(
        task=definition,
        handler=lambda: None,
        context=run_context,
    )

    assert definition == before
