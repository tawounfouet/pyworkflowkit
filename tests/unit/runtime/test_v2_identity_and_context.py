"""LOT-01 unit tests for V2 execution identity and correlation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)


def test_execution_ids_are_distinct_runtime_types() -> None:
    workflow_run_id = WorkflowRunId.parse("same-text")
    task_run_id = TaskRunId.parse("same-text")
    task_attempt_id = TaskAttemptId.parse("same-text")

    assert str(workflow_run_id) == "same-text"
    assert str(task_run_id) == "same-text"
    assert str(task_attempt_id) == "same-text"

    assert type(workflow_run_id) is WorkflowRunId
    assert type(task_run_id) is TaskRunId
    assert type(task_attempt_id) is TaskAttemptId

    assert workflow_run_id != task_run_id
    assert task_run_id != task_attempt_id
    assert workflow_run_id != task_attempt_id


def test_execution_ids_are_immutable_and_parse_without_normalizing() -> None:
    run_id = WorkflowRunId.parse("W-42")

    with pytest.raises(FrozenInstanceError):
        run_id.value = "W-43"  # type: ignore[misc]

    assert str(run_id) == "W-42"


def test_new_identifiers_are_non_empty_and_independent() -> None:
    first = TaskAttemptId.new()
    second = TaskAttemptId.new()

    assert str(first)
    assert str(second)
    assert first != second


@pytest.mark.parametrize(
    "identifier_type",
    [WorkflowRunId, TaskRunId, TaskAttemptId, CorrelationId],
)
def test_identifier_rejects_blank_values(identifier_type: type[object]) -> None:
    with pytest.raises(ValueError):
        identifier_type("   ")  # type: ignore[call-arg]


def test_correlation_context_keeps_native_identity_fields_separate() -> None:
    correlation = CorrelationContext(
        correlation_id=CorrelationId.parse("C-42"),
        causation_id="request-17",
        workflow_run_id="W-42",
        task_run_id="TR-17",
        task_attempt_id="TA-3",
        ingestion_run_id="I-288",
        transformation_execution_id="T-913",
    )

    assert str(correlation.correlation_id) == "C-42"
    assert correlation.workflow_run_id == "W-42"
    assert correlation.task_run_id == "TR-17"
    assert correlation.task_attempt_id == "TA-3"
    assert correlation.ingestion_run_id == "I-288"
    assert correlation.transformation_execution_id == "T-913"


def test_with_trace_preserves_execution_correlation() -> None:
    original = CorrelationContext(
        correlation_id=CorrelationId.parse("C-42"),
        workflow_run_id="W-42",
    )

    traced = original.with_trace(trace_id="trace-1", span_id="span-1")

    assert traced.correlation_id == original.correlation_id
    assert traced.workflow_run_id == "W-42"
    assert traced.trace_id == "trace-1"
    assert traced.span_id == "span-1"
    assert original.trace_id is None
