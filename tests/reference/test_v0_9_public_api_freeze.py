"""RQ-01 acceptance for the PyWorkflowKit 1.0 public API freeze."""

from __future__ import annotations

import json
from importlib import import_module

from pyworkflowkit.compatibility import ACTIVE_DEPRECATIONS
from pyworkflowkit.public_api import (
    PUBLIC_API_CONTRACT_VERSION,
    PUBLIC_API_SURFACES,
    PUBLIC_API_TARGET_RELEASE,
    public_api_contract_snapshot,
)


def test_rq01_contract_targets_1_0() -> None:
    assert PUBLIC_API_CONTRACT_VERSION == "1"
    assert PUBLIC_API_TARGET_RELEASE == "1.0.0"


def test_rq01_only_intentional_facades_are_frozen() -> None:
    assert tuple(sorted(PUBLIC_API_SURFACES)) == (
        "pyworkflowkit",
        "pyworkflowkit.control_plane",
        "pyworkflowkit.ecosystem",
        "pyworkflowkit.integrations",
        "pyworkflowkit.plugins",
        "pyworkflowkit.public_api",
    )


def test_rq01_frozen_facades_match_exported_symbols() -> None:
    for module_name, expected_symbols in PUBLIC_API_SURFACES.items():
        # The package-root tuple is the historical 1.0 migration baseline.
        # PyWorkflowKit 2.0 intentionally replaces that root at its RC freeze.
        if module_name == "pyworkflowkit":
            assert len(expected_symbols) == len(set(expected_symbols))
            continue

        module = import_module(module_name)
        exported = tuple(module.__all__)

        assert len(exported) == len(set(exported)), module_name
        assert set(exported) == set(expected_symbols), module_name

        for symbol in expected_symbols:
            assert hasattr(module, symbol), f"{module_name}.{symbol}"


def test_rq01_snapshot_is_deterministic_and_json_serializable() -> None:
    snapshot = public_api_contract_snapshot()

    assert snapshot["contract_version"] == "1"
    assert snapshot["target_release"] == "1.0.0"
    assert tuple(snapshot["surfaces"]) == tuple(sorted(PUBLIC_API_SURFACES))
    assert json.loads(json.dumps(snapshot, sort_keys=True)) == snapshot


def test_rq01_starts_without_active_api_removals() -> None:
    assert ACTIVE_DEPRECATIONS == ()
