"""Tests for execution-port value contracts."""

from operator import setitem

import pytest

from pyworkflowkit.domain.ids import (
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.ports.executor import ExecutorCapabilities, RunContext


def test_executor_capabilities_default_to_conservative_false() -> None:
    capabilities = ExecutorCapabilities()

    assert capabilities.supports_parallelism is False
    assert capabilities.supports_hard_timeout is False
    assert capabilities.supports_hard_cancellation is False


def test_run_context_defensively_copies_mappings() -> None:
    parameters = {"source": "input.csv"}
    dependency_outputs = {TaskId("fetch"): {"rows": 10}}

    context = RunContext(
        workflow_run_id=WorkflowRunId("run-1"),
        task_run_id=TaskRunId("task-run-1"),
        attempt_id=TaskAttemptId("attempt-1"),
        task_id=TaskId("transform"),
        attempt_number=1,
        workflow_parameters=parameters,
        dependency_outputs=dependency_outputs,
    )

    parameters["source"] = "changed.csv"
    dependency_outputs[TaskId("fetch")] = {"rows": 99}

    assert context.workflow_parameters["source"] == "input.csv"
    assert context.dependency_outputs[TaskId("fetch")] == {"rows": 10}

    with pytest.raises(TypeError):
        setitem(context.workflow_parameters, "source", "mutated.csv")


def test_run_context_rejects_non_positive_attempt_number() -> None:
    with pytest.raises(ValueError, match="attempt_number"):
        RunContext(
            workflow_run_id=WorkflowRunId("run-1"),
            task_run_id=TaskRunId("task-run-1"),
            attempt_id=TaskAttemptId("attempt-1"),
            task_id=TaskId("task"),
            attempt_number=0,
        )
