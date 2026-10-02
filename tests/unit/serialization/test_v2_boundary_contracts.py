"""LOT-01 tests for pre-freeze portable wire-contract identities."""

from __future__ import annotations

import json

from pyworkflowkit.serialization import (
    V2_BOUNDARY_WIRE_CONTRACTS,
    v2_boundary_wire_contract_snapshot,
)


def test_boundary_wire_contracts_have_independent_versions() -> None:
    assert V2_BOUNDARY_WIRE_CONTRACTS["correlation_context"].contract == (
        "pykit.correlation_context"
    )
    assert V2_BOUNDARY_WIRE_CONTRACTS["failure_evidence"].owner == "pykit"
    assert V2_BOUNDARY_WIRE_CONTRACTS["external_run_ref"].owner == "pyworkflowkit"

    for descriptor in V2_BOUNDARY_WIRE_CONTRACTS.values():
        assert descriptor.contract_version == "1"


def test_boundary_wire_contract_snapshot_is_deterministic_json() -> None:
    snapshot = v2_boundary_wire_contract_snapshot()

    assert snapshot["contract_family_version"] == "1"
    assert json.loads(json.dumps(snapshot, sort_keys=True)) == snapshot
