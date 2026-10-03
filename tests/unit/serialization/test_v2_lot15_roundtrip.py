"""LOT-15 roundtrip tests for canonical V2 boundary serialization."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from pyworkflowkit.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.lineage import ManifestAttempt, ManifestTaskRun, RunManifest
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    ExternalRunRef,
    RuntimeEvent,
    RuntimeEventType,
    TaskAttemptId,
    TaskOutputCheckpoint,
    TaskRunId,
    WorkflowExecutionReference,
    WorkflowRunId,
)
from pyworkflowkit.serialization import (
    BoundaryCodec,
    CorrelationContextSchema,
    SchemaCodec,
    WireContractError,
    WireContractMismatchError,
    WirePayloadTooLargeError,
    canonical_json,
)
from pyworkflowkit.states import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus

T0 = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


def _correlation() -> CorrelationContext:
    return CorrelationContext(
        correlation_id=CorrelationId.parse("C-15"),
        causation_id="cause-14",
        workflow_run_id="W-15",
        task_run_id="TR-15",
        task_attempt_id="TA-15",
        trace_id="trace-15",
        span_id="span-15",
    )


def _external() -> ExternalRunRef:
    return ExternalRunRef(
        provider="example",
        external_run_id="remote-15",
        kind="job",
        status_hint="RUNNING",
        status_locator="jobs/remote-15",
        correlation_id=CorrelationId.parse("C-15"),
        causation_id="cause-14",
        metadata=(("region", "eu-west-3"),),
    )


def _values() -> tuple[object, ...]:
    correlation = _correlation()
    external = _external()
    failure = FailureEvidence(
        error_code="REMOTE_TIMEOUT",
        category=FailureCategory.TIMEOUT,
        retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
        uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
        correlation_id=correlation.correlation_id,
        workflow_run_id="W-15",
        task_run_id="TR-15",
        task_attempt_id="TA-15",
        external_run=external,
        source_component="integration.example",
        provider_code="504",
        message_summary="provider response timed out",
        occurred_at=T0,
        details=(("attempt", "1"),),
    )
    diagnostic = Diagnostic(
        code="PWK-LOT15",
        severity=DiagnosticSeverity.WARNING,
        summary="wire evidence",
        details=(("key", "value"),),
        workflow_run_id="W-15",
        correlation_id=correlation.correlation_id,
        source_component="serialization",
    )
    event = RuntimeEvent(
        sequence=7,
        event_id="W-15:event-7",
        event_type=RuntimeEventType.TASK_SUCCEEDED,
        workflow_run_id=WorkflowRunId.parse("W-15"),
        task_run_id=TaskRunId.parse("TR-15"),
        attempt_id=TaskAttemptId.parse("TA-15"),
        task_key="load",
        attempt_number=1,
        occurred_at=T0,
        from_status="RUNNING",
        to_status="SUCCEEDED",
        payload={"rows": 3, "nested": {"ok": True}},
    )
    checkpoint = TaskOutputCheckpoint(
        task_run_id=TaskRunId.parse("TR-15"),
        output={"rows": [1, 2, 3], "ok": True},
        recorded_at=T0,
    )
    manifest = RunManifest(
        schema_version="2",
        workflow_run_id=WorkflowRunId.parse("W-15"),
        workflow_name="lot15",
        workflow_version="1",
        definition_fingerprint="sha256:def",
        plan_fingerprint="sha256:plan",
        status=WorkflowRunStatus.SUCCEEDED,
        created_at=T0.isoformat(),
        started_at=T0.isoformat(),
        ended_at=T0.isoformat(),
        tasks=(
            ManifestTaskRun(
                task_run_id=TaskRunId.parse("TR-15"),
                task_key="load",
                status=TaskRunStatus.SUCCEEDED,
                attempts=(
                    ManifestAttempt(
                        attempt_id=TaskAttemptId.parse("TA-15"),
                        attempt_number=1,
                        status=TaskAttemptStatus.SUCCEEDED,
                    ),
                ),
                external_runs=(external,),
                output={"rows": (1, 2, 3)},
                output_digest="sha256:demo",
                output_recorded_at=T0.isoformat(),
            ),
        ),
    )
    workflow_ref = WorkflowExecutionReference(
        workflow_run_id=WorkflowRunId.parse("W-15"),
        workflow_definition_id="wf-lot15",
        status="SUCCEEDED",
        started_at=T0,
    )
    return (
        correlation,
        workflow_ref,
        external,
        failure,
        diagnostic,
        event,
        checkpoint,
        manifest,
    )


@pytest.mark.parametrize("value", _values())
def test_boundary_codec_roundtrips_canonical_v2_values(value: object) -> None:
    codec = BoundaryCodec()

    encoded = codec.encode(value)  # type: ignore[arg-type]
    restored = codec.decode(encoded)

    assert type(restored) is type(value)
    assert codec.encode(restored) == encoded


def test_boundary_codec_decode_as_preserves_expected_type() -> None:
    codec = BoundaryCodec()
    value = _correlation()

    restored = codec.decode_as(CorrelationContext, codec.encode(value))

    assert restored == value


def test_decode_as_rejects_wrong_contract_type() -> None:
    codec = BoundaryCodec()
    encoded = codec.encode(_external())

    with pytest.raises(WireContractMismatchError, match="expected CorrelationContext"):
        codec.decode_as(CorrelationContext, encoded)


def test_canonical_json_is_sorted_compact_unicode_and_finite() -> None:
    assert canonical_json({"z": "é", "a": [2, 1]}) == '{"a":[2,1],"z":"é"}'

    with pytest.raises(ValueError, match="non-finite"):
        canonical_json({"bad": float("nan")})
    with pytest.raises(TypeError, match="mapping keys"):
        canonical_json({1: "bad"})
    with pytest.raises(TypeError, match="unsupported"):
        canonical_json({"bad": object()})


def test_schema_codec_is_strict_extra_forbidden_and_canonical() -> None:
    schema = CorrelationContextSchema(correlation_id="C-15")
    encoded = SchemaCodec.to_json(schema)

    assert encoded == (
        '{"causation_id":null,"correlation_id":"C-15","ingestion_run_id":null,'
        '"parent_execution_id":null,"span_id":null,"task_attempt_id":null,'
        '"task_run_id":null,"trace_id":null,"transformation_execution_id":null,'
        '"workflow_run_id":null}'
    )
    assert SchemaCodec.to_bytes(schema) == encoded.encode("utf-8")
    assert SchemaCodec.from_json(CorrelationContextSchema, encoded) == schema

    with pytest.raises(ValidationError):
        SchemaCodec.from_json(
            CorrelationContextSchema,
            '{"correlation_id":"C-15","unexpected":true}',
        )


def test_wire_timestamp_is_canonical_utc() -> None:
    value = WorkflowExecutionReference(
        workflow_run_id=WorkflowRunId.parse("W-15"),
        workflow_definition_id="wf",
        started_at=datetime.fromisoformat("2026-10-03T11:00:00+02:00"),
    )

    encoded = BoundaryCodec().encode(value)

    assert '"started_at":"2026-10-03T09:00:00Z"' in encoded


def test_boundary_codec_rejects_malformed_unknown_future_and_oversized_payloads() -> None:
    codec = BoundaryCodec(max_payload_bytes=256)

    with pytest.raises(WireContractError, match="invalid V2 wire envelope"):
        codec.decode("{not-json")

    unknown = '{"contract":"unknown.contract","contract_version":"1","payload":{}}'
    with pytest.raises(WireContractMismatchError, match="unknown V2 wire contract"):
        codec.decode(unknown)

    future = (
        '{"contract":"pykit.correlation_context","contract_version":"999",'
        '"payload":{"correlation_id":"C-15"}}'
    )
    with pytest.raises(ValueError, match="no explicit migration path"):
        codec.decode(future)

    with pytest.raises(WirePayloadTooLargeError):
        codec.decode("x" * 257)


def test_boundary_codec_rejects_invalid_utf8() -> None:
    with pytest.raises(WireContractError, match="valid UTF-8"):
        BoundaryCodec().decode(b"\xff\xfe")


def test_boundary_codec_rejects_embedded_contract_version_drift() -> None:
    value = ExternalRunRef(
        provider="example",
        external_run_id="R-1",
        kind="job",
        contract_version="999",
    )

    with pytest.raises(WireContractMismatchError, match="does not match"):
        BoundaryCodec().encode(value)
