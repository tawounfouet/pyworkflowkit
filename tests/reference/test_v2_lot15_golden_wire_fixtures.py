"""Golden wire fixtures for the finalized LOT-15 canonical JSON contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from pyworkflowkit.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.lineage import RunManifest
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    ExternalRunRef,
    RuntimeEvent,
    RuntimeEventType,
    TaskOutputCheckpoint,
    TaskRunId,
    WorkflowExecutionReference,
    WorkflowRunId,
)
from pyworkflowkit.serialization import BoundaryCodec
from pyworkflowkit.states import WorkflowRunStatus

FIXTURES = Path(__file__).parents[1] / "fixtures" / "v2" / "serialization"
T0 = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


def _golden_values() -> dict[str, object]:
    return {
        "correlation_context.json": CorrelationContext(
            correlation_id=CorrelationId.parse("C-golden"),
        ),
        "workflow_execution_reference.json": WorkflowExecutionReference(
            workflow_run_id=WorkflowRunId.parse("W-golden"),
            workflow_definition_id="wf-golden",
            started_at=T0,
        ),
        "external_run_ref.json": ExternalRunRef(
            provider="example",
            external_run_id="remote-golden",
            kind="job",
        ),
        "failure_evidence.json": FailureEvidence(
            error_code="E-GOLDEN",
            category=FailureCategory.INTERNAL,
            retryability=Retryability.NON_RETRYABLE,
            uncertainty=OutcomeUncertainty.KNOWN,
            correlation_id=CorrelationId.parse("C-golden"),
            occurred_at=T0,
        ),
        "diagnostic.json": Diagnostic(
            code="D-GOLDEN",
            severity=DiagnosticSeverity.WARNING,
            summary="golden diagnostic",
        ),
        "runtime_event.json": RuntimeEvent(
            sequence=1,
            event_id="W-golden:event-1",
            event_type=RuntimeEventType.WORKFLOW_STARTED,
            workflow_run_id=WorkflowRunId.parse("W-golden"),
            occurred_at=T0,
            from_status="PENDING",
            to_status="RUNNING",
        ),
        "task_output_checkpoint.json": TaskOutputCheckpoint(
            task_run_id=TaskRunId.parse("TR-golden"),
            output={"ok": True},
            recorded_at=T0,
        ),
        "run_manifest.json": RunManifest(
            schema_version="2",
            workflow_run_id=WorkflowRunId.parse("W-golden"),
            workflow_name="golden",
            workflow_version="1",
            definition_fingerprint="sha256:def",
            plan_fingerprint="sha256:plan",
            status=WorkflowRunStatus.SUCCEEDED,
            created_at=T0.isoformat(),
            started_at=T0.isoformat(),
            ended_at=T0.isoformat(),
            tasks=(),
        ),
    }


@pytest.mark.parametrize(("fixture_name", "value"), tuple(_golden_values().items()))
def test_golden_fixture_matches_canonical_bytes(
    fixture_name: str,
    value: object,
) -> None:
    codec = BoundaryCodec()
    expected = (FIXTURES / fixture_name).read_bytes()

    actual = codec.encode_bytes(value)  # type: ignore[arg-type]

    assert actual == expected
    restored = codec.decode(expected)
    assert codec.encode_bytes(restored) == expected
