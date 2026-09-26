"""Tests for execution-port value contracts."""

from operator import setitem

import pytest

from pyworkflowkit.domain.ids import (
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    ExecutorCapabilities,
    RunContext,
    TimeoutCapability,
)


def test_executor_capabilities_default_to_conservative_local_contract() -> None:
    capabilities = ExecutorCapabilities()

    assert capabilities.supports_parallelism is False
    assert capabilities.timeout is TimeoutCapability.NONE
    assert capabilities.cancellation is CancellationCapability.NONE
    assert capabilities.max_concurrency == 1
    assert capabilities.supports_timeout is False
    assert capabilities.supports_cancellation is False
    assert capabilities.supports_hard_timeout is False
    assert capabilities.supports_hard_cancellation is False


def test_executor_capabilities_expose_strength_and_compatibility_views() -> None:
    capabilities = ExecutorCapabilities(
        supports_parallelism=True,
        timeout=TimeoutCapability.HARD,
        cancellation=CancellationCapability.COOPERATIVE,
        max_concurrency=8,
    )

    assert capabilities.supports_timeout is True
    assert capabilities.supports_hard_timeout is True
    assert capabilities.supports_cancellation is True
    assert capabilities.supports_hard_cancellation is False


def test_non_parallel_executor_rejects_multiple_concurrency_slots() -> None:
    with pytest.raises(ValueError, match="max_concurrency=1"):
        ExecutorCapabilities(
            supports_parallelism=False,
            max_concurrency=2,
        )


@pytest.mark.parametrize("max_concurrency", [0, -1])
def test_executor_capabilities_reject_non_positive_max_concurrency(
    max_concurrency: int,
) -> None:
    with pytest.raises(ValueError, match="max_concurrency"):
        ExecutorCapabilities(
            supports_parallelism=True,
            max_concurrency=max_concurrency,
        )


def test_executor_capabilities_reject_boolean_max_concurrency() -> None:
    with pytest.raises(TypeError, match="max_concurrency"):
        ExecutorCapabilities(max_concurrency=True)


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


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("workflow_run_id", {"workflow_run_id": WorkflowRunId("")}),
        ("task_run_id", {"task_run_id": TaskRunId(" ")}),
        ("attempt_id", {"attempt_id": TaskAttemptId("")}),
        ("task_id", {"task_id": TaskId(" ")}),
    ],
)
def test_run_context_rejects_blank_identity(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "workflow_run_id": WorkflowRunId("run-1"),
        "task_run_id": TaskRunId("task-run-1"),
        "attempt_id": TaskAttemptId("attempt-1"),
        "task_id": TaskId("task"),
        "attempt_number": 1,
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=field_name):
        RunContext(**values)  # type: ignore[arg-type]


def test_run_context_rejects_boolean_attempt_number() -> None:
    with pytest.raises(TypeError, match="attempt_number"):
        RunContext(
            workflow_run_id=WorkflowRunId("run-1"),
            task_run_id=TaskRunId("task-run-1"),
            attempt_id=TaskAttemptId("attempt-1"),
            task_id=TaskId("task"),
            attempt_number=True,
        )
