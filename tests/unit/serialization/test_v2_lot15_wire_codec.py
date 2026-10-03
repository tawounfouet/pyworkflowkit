"""LOT-15 qualification for strict versioned boundary wire codecs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

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
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    ExternalRunRef,
    WorkflowExecutionReference,
    WorkflowRunId,
)
from pyworkflowkit.serialization import (
    BoundaryUpcasterRegistry,
    BoundaryWireCodec,
    CorrelationContextSchema,
    WireContractError,
)

_FIXTURES = Path(__file__).parents[2] / "fixtures" / "v2_serialization"


def _external_ref() -> ExternalRunRef:
    return ExternalRunRef(
        provider="pytransformkit",
        external_run_id="T-913",
        kind="transformation_execution",
        status_hint="running",
        correlation_id=CorrelationId.parse("C-42"),
        metadata=(("job", "daily"), ("region", "eu")),
    )


def _samples() -> dict[str, object]:
    external = _external_ref()
    return {
        "correlation_context": CorrelationContext(
            correlation_id=CorrelationId.parse("C-42"),
            causation_id="cause-1",
            workflow_run_id="W-42",
            trace_id="trace-1",
            span_id="span-1",
        ),
        "workflow_execution_reference": WorkflowExecutionReference(
            workflow_run_id=WorkflowRunId.parse("W-42"),
            workflow_definition_id="orders",
            status="RUNNING",
            started_at=datetime(2026, 10, 3, 9, 15, 30, tzinfo=UTC),
        ),
        "external_run_ref": external,
        "failure_evidence": FailureEvidence(
            error_code="PWK-EXT-UNKNOWN",
            category=FailureCategory.UNKNOWN_OUTCOME,
            retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
            uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
            correlation_id=CorrelationId.parse("C-42"),
            workflow_run_id="W-42",
            task_run_id="TR-17",
            task_attempt_id="TA-3",
            external_run=external,
            source_component="pytransformkit-adapter",
            message_summary="provider outcome is not yet known",
            occurred_at=datetime(2026, 10, 3, 9, 16, tzinfo=UTC),
            details=(("provider", "pytransformkit"),),
        ),
        "diagnostic": Diagnostic(
            code="PWK-RETRY-001",
            severity=DiagnosticSeverity.INFO,
            summary="retry deferred until reconciliation",
            details=(("provider", "pytransformkit"),),
            workflow_run_id="W-42",
            task_run_id="TR-17",
            task_attempt_id="TA-3",
            correlation_id=CorrelationId.parse("C-42"),
            source_component="retry_evaluator",
            decision_context="unknown_outcome",
            related_policy="RetryPolicy",
        ),
    }


@pytest.mark.parametrize("name", sorted(_samples()))
def test_lot15_golden_fixture_is_exact_and_round_trips(name: str) -> None:
    codec = BoundaryWireCodec()
    value = _samples()[name]
    expected = (_FIXTURES / f"{name}_v1.json").read_text().strip()

    encoded = codec.encode(value)  # type: ignore[arg-type]
    restored = codec.decode(encoded)

    assert encoded == expected
    assert restored == value
    assert codec.encode(restored) == expected
    assert codec.encode_bytes(restored) == expected.encode("utf-8")


def test_lot15_decode_as_enforces_expected_domain_type() -> None:
    codec = BoundaryWireCodec()
    payload = codec.encode(_samples()["correlation_context"])  # type: ignore[arg-type]

    restored = codec.decode_as(CorrelationContext, payload)
    assert restored == _samples()["correlation_context"]

    with pytest.raises(WireContractError, match="expected ExternalRunRef"):
        codec.decode_as(ExternalRunRef, payload)


def test_lot15_schema_is_strict_and_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        CorrelationContextSchema(correlation_id=42)  # type: ignore[arg-type]

    codec = BoundaryWireCodec()
    payload = (
        '{"contract":"pykit.correlation_context","contract_version":"1",'
        '"payload":{"correlation_id":"C-1","unexpected":true}}'
    )
    with pytest.raises(WireContractError, match="invalid .* payload"):
        codec.decode(payload)


def test_lot15_rejects_unknown_contract_and_unmigrated_version() -> None:
    codec = BoundaryWireCodec()

    with pytest.raises(WireContractError, match="unknown boundary contract"):
        codec.decode(
            '{"contract":"unknown.contract","contract_version":"1","payload":{}}'
        )

    with pytest.raises(WireContractError, match="no upcaster"):
        codec.decode(
            '{"contract":"pykit.correlation_context","contract_version":"0",'
            '"payload":{"correlation_id":"C-1"}}'
        )


def test_lot15_upcaster_hook_migrates_to_current_contract() -> None:
    upcasters = BoundaryUpcasterRegistry()
    upcasters.register(
        contract="pykit.correlation_context",
        from_version="0",
        to_version="1",
        upcaster=lambda payload: {"correlation_id": payload["id"]},
    )
    codec = BoundaryWireCodec(upcasters=upcasters)

    legacy = (
        '{"contract":"pykit.correlation_context","contract_version":"0",'
        '"payload":{"id":"C-legacy"}}'
    )
    restored = codec.decode_as(CorrelationContext, legacy)

    assert restored.correlation_id == CorrelationId.parse("C-legacy")
    assert codec.canonicalize(legacy) == (
        '{"contract":"pykit.correlation_context","contract_version":"1",'
        '"payload":{"correlation_id":"C-legacy"}}'
    )


def test_lot15_upcaster_registry_rejects_duplicates_cycles_and_bad_results() -> None:
    registry = BoundaryUpcasterRegistry()
    registry.register(
        contract="pykit.correlation_context",
        from_version="0",
        to_version="1",
        upcaster=lambda payload: dict(payload),
    )
    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            contract="pykit.correlation_context",
            from_version="0",
            to_version="1",
            upcaster=lambda payload: dict(payload),
        )
    with pytest.raises(ValueError, match="must differ"):
        registry.register(
            contract="pykit.correlation_context",
            from_version="1",
            to_version="1",
            upcaster=lambda payload: dict(payload),
        )

    cyclic = BoundaryUpcasterRegistry()
    cyclic.register(
        contract="pykit.correlation_context",
        from_version="0",
        to_version="x",
        upcaster=lambda payload: dict(payload),
    )
    cyclic.register(
        contract="pykit.correlation_context",
        from_version="x",
        to_version="0",
        upcaster=lambda payload: dict(payload),
    )
    with pytest.raises(WireContractError, match="cycle"):
        cyclic.upcast(
            contract="pykit.correlation_context",
            from_version="0",
            to_version="1",
            payload={"id": "C-1"},
        )

    bad = BoundaryUpcasterRegistry()
    bad.register(
        contract="pykit.correlation_context",
        from_version="0",
        to_version="1",
        upcaster=lambda payload: "not-a-mapping",  # type: ignore[arg-type,return-value]
    )
    with pytest.raises(WireContractError, match="must return a mapping"):
        bad.upcast(
            contract="pykit.correlation_context",
            from_version="0",
            to_version="1",
            payload={"id": "C-1"},
        )


def test_lot15_rejects_duplicate_json_keys_and_nonfinite_numbers() -> None:
    codec = BoundaryWireCodec()

    duplicate = (
        '{"contract":"pykit.correlation_context",'
        '"contract":"pykit.correlation_context","contract_version":"1",'
        '"payload":{"correlation_id":"C-1"}}'
    )
    with pytest.raises(WireContractError, match="duplicate JSON object key"):
        codec.decode(duplicate)

    nonfinite = (
        '{"contract":"pykit.correlation_context","contract_version":"1",'
        '"payload":{"correlation_id":"C-1","extra":NaN}}'
    )
    with pytest.raises(WireContractError, match="non-finite"):
        codec.decode(nonfinite)


def test_lot15_payload_size_depth_and_utf8_limits_fail_closed() -> None:
    sample = _samples()["correlation_context"]

    small = BoundaryWireCodec(max_payload_bytes=32)
    with pytest.raises(WireContractError, match="byte limit"):
        small.encode(sample)  # type: ignore[arg-type]

    shallow = BoundaryWireCodec(max_nesting_depth=2)
    payload = (
        '{"contract":"pykit.correlation_context","contract_version":"1",'
        '"payload":{"correlation_id":"C-1"}}'
    )
    with pytest.raises(WireContractError, match="nesting depth"):
        shallow.decode(payload)

    codec = BoundaryWireCodec()
    with pytest.raises(WireContractError, match="valid UTF-8"):
        codec.decode(b"\xff\xfe")


def test_lot15_rejects_non_object_envelope_and_invalid_json() -> None:
    codec = BoundaryWireCodec()

    with pytest.raises(WireContractError, match="invalid wire envelope"):
        codec.decode("[]")
    with pytest.raises(WireContractError, match="invalid canonical JSON"):
        codec.decode("{not-json}")


def test_lot15_encode_rejects_unknown_type_wrong_version_and_duplicate_pairs() -> None:
    codec = BoundaryWireCodec()

    with pytest.raises(WireContractError, match="unsupported boundary value type"):
        codec.encode(object())  # type: ignore[arg-type]

    wrong_version = ExternalRunRef(
        provider="provider",
        external_run_id="run-1",
        kind="job",
        contract_version="2",
    )
    with pytest.raises(WireContractError, match="expected '1'"):
        codec.encode(wrong_version)

    duplicate_metadata = ExternalRunRef(
        provider="provider",
        external_run_id="run-1",
        kind="job",
        metadata=(("key", "one"), ("key", "two")),
    )
    with pytest.raises(ValueError, match="duplicate key"):
        codec.encode(duplicate_metadata)


def test_lot15_canonical_json_is_stable_under_input_key_order() -> None:
    codec = BoundaryWireCodec()
    expected = (_FIXTURES / "external_run_ref_v1.json").read_text().strip()
    parsed = json.loads(expected)
    reordered = json.dumps(
        {
            "payload": parsed["payload"],
            "contract_version": parsed["contract_version"],
            "contract": parsed["contract"],
        },
        indent=2,
    )

    assert codec.canonicalize(reordered) == expected
