"""LOT-15 reference acceptance for strict V2 serialization contracts."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.serialization as serialization


def test_lot15_wire_contract_registry_is_finalized_and_additive() -> None:
    snapshot = serialization.v2_boundary_wire_contract_snapshot()

    assert snapshot["contract_family_version"] == "1"
    assert snapshot["codec"] == "canonical_json_utf8"
    assert snapshot["strict_unknown_fields"] is True
    assert snapshot["implicit_migrations"] is False

    assert tuple(sorted(serialization.V2_BOUNDARY_WIRE_CONTRACTS)) == (
        "correlation_context",
        "diagnostic",
        "external_run_ref",
        "failure_evidence",
        "run_manifest",
        "runtime_event",
        "task_output_checkpoint",
        "workflow_execution_reference",
    )


def test_lot15_qualified_serialization_surface_is_explicit() -> None:
    expected = {
        "BoundaryCodec",
        "CorrelationContextSchema",
        "DiagnosticSchema",
        "ExternalRunRefSchema",
        "FailureEvidenceSchema",
        "RunManifestSchema",
        "RuntimeEventSchema",
        "SchemaCodec",
        "StrictSchema",
        "TaskOutputCheckpointSchema",
        "WireEnvelope",
        "WireMigrationRegistry",
        "WorkflowExecutionReferenceSchema",
        "canonical_json",
    }
    assert expected.issubset(set(serialization.__all__))

    for name in expected:
        assert name not in pyworkflowkit.__all__


def test_lot15_current_contract_versions_are_independent_and_explicit() -> None:
    for descriptor in serialization.V2_BOUNDARY_WIRE_CONTRACTS.values():
        assert descriptor.contract_version == "1"
        assert descriptor.contract
        assert descriptor.owner


def test_lot15_codec_has_bounded_default_and_utf8_canonical_contract() -> None:
    codec = serialization.BoundaryCodec()

    assert codec.max_payload_bytes == serialization.DEFAULT_MAX_WIRE_BYTES
    assert serialization.canonical_json({"é": 1, "a": 2}) == '{"a":2,"é":1}'
