"""LOT-15 reference acceptance for strict versioned V2 wire contracts."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.serialization as serialization


def test_lot15_qualified_serialization_surface_is_explicit() -> None:
    expected = {
        "BoundaryContractSpec",
        "BoundaryUpcasterRegistry",
        "BoundaryWireCodec",
        "BoundaryValue",
        "CorrelationContextSchema",
        "DiagnosticSchema",
        "ExternalRunRefSchema",
        "FailureEvidenceSchema",
        "StrictBoundarySchema",
        "WireContractError",
        "WireEnvelopeSchema",
        "WorkflowExecutionReferenceSchema",
        "boundary_contract_specs",
    }
    assert expected.issubset(set(serialization.__all__))

    for name in expected:
        assert name not in pyworkflowkit.__all__


def test_lot15_contract_registry_is_exact_and_non_dynamic() -> None:
    specs = serialization.boundary_contract_specs()

    assert tuple(specs) == (
        "correlation_context",
        "diagnostic",
        "external_run_ref",
        "failure_evidence",
        "workflow_execution_reference",
    )
    assert {spec.descriptor.contract for spec in specs.values()} == {
        "pykit.correlation_context",
        "pykit.failure_evidence",
        "pyworkflowkit.diagnostic",
        "pyworkflowkit.external_run_ref",
        "pyworkflowkit.workflow_execution_reference",
    }
    assert all(spec.descriptor.contract_version == "1" for spec in specs.values())


def test_lot15_wire_contract_snapshot_freezes_codec_rules() -> None:
    snapshot = serialization.v2_boundary_wire_contract_snapshot()

    assert snapshot["contract_family_version"] == "1"
    assert snapshot["codec_contract_version"] == "1"
    assert snapshot["canonical_json"] is True
    assert snapshot["strict_decoding"] is True
    assert snapshot["non_executable_deserialization"] is True
    assert snapshot["duplicate_json_keys"] == "reject"
    assert snapshot["non_finite_numbers"] == "reject"
    assert snapshot["default_max_payload_bytes"] == 1_048_576
    assert snapshot["default_max_nesting_depth"] == 32
    assert snapshot["envelope_fields"] == [
        "contract",
        "contract_version",
        "payload",
    ]


def test_lot15_transitional_aliases_point_to_v2_not_legacy_codec() -> None:
    assert serialization.SchemaCodec is serialization.BoundaryWireCodec
    assert serialization.StrictSchema is serialization.StrictBoundarySchema


def test_lot15_codec_defaults_match_snapshot() -> None:
    codec = serialization.BoundaryWireCodec()

    assert codec.max_payload_bytes == serialization.DEFAULT_MAX_PAYLOAD_BYTES
    assert codec.max_nesting_depth == serialization.DEFAULT_MAX_NESTING_DEPTH
    assert codec.max_payload_bytes == 1_048_576
    assert codec.max_nesting_depth == 32
