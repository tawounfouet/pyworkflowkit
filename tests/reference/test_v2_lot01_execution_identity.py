"""LOT-01 acceptance for execution identity and shared boundary values."""

from __future__ import annotations

from pyworkflowkit.diagnostics import (
    Diagnostic,
    FailureEvidence,
    OutcomeUncertainty,
)
from pyworkflowkit.policies import RetryDecision
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    ExternalRunRef,
    TaskAttemptId,
    TaskRunId,
    WorkflowExecutionReference,
    WorkflowRunId,
)
from pyworkflowkit.serialization import V2_BOUNDARY_WIRE_CONTRACTS


def test_lot01_public_qualified_surfaces_are_available() -> None:
    assert WorkflowRunId
    assert TaskRunId
    assert TaskAttemptId
    assert CorrelationId
    assert CorrelationContext
    assert WorkflowExecutionReference
    assert ExternalRunRef
    assert FailureEvidence
    assert Diagnostic
    assert RetryDecision
    assert OutcomeUncertainty
    assert V2_BOUNDARY_WIRE_CONTRACTS


def test_lot01_has_no_universal_run_id() -> None:
    import pyworkflowkit.runtime as runtime

    assert "RunId" not in runtime.__all__
    assert not hasattr(runtime, "RunId")


def test_lot01_correlation_does_not_replace_native_identity() -> None:
    workflow_run_id = WorkflowRunId.parse("W-42")
    task_run_id = TaskRunId.parse("TR-17")
    task_attempt_id = TaskAttemptId.parse("TA-3")
    correlation_id = CorrelationId.parse("C-42")

    assert str(workflow_run_id) != str(correlation_id)
    assert type(workflow_run_id) is not type(task_run_id)
    assert type(task_run_id) is not type(task_attempt_id)
    assert type(task_attempt_id) is not type(correlation_id)
