"""PyWorkflowKit 2.0 stable-promotion compatibility and evidence contract."""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from typing import cast

from pyworkflowkit._compat.v1_to_v2 import migration_contract_snapshot
from pyworkflowkit.contracts.v2_release_candidate import (
    V2_RC_REQUIRED_QUALIFICATION_FAMILIES,
    V2_RELEASE_CANDIDATE_VERSION,
    V2_STABLE_IDENTITIES,
    V2_STABLE_PROTOCOLS,
    V2_SUPPORTED_PYTHON_VERSIONS,
    v2_release_candidate_evidence_manifest,
)
from pyworkflowkit.executors.contracts import v2_executor_contract_snapshot
from pyworkflowkit.integrations.pyingestkit import v2_pyingestkit_integration_snapshot
from pyworkflowkit.integrations.pytransformkit import v2_pytransformkit_integration_snapshot
from pyworkflowkit.migrations.contract import MIGRATION_HEAD_REVISION
from pyworkflowkit.persistence.contracts import v2_metadata_store_contract_snapshot
from pyworkflowkit.public_api import v2_root_public_api_snapshot
from pyworkflowkit.serialization import v2_boundary_wire_contract_snapshot
from pyworkflowkit.states.contracts import v2_state_contract_snapshot

V2_STABLE_CONTRACT_VERSION = "1"
V2_STABLE_VERSION = "2.0.0"
V2_STABLE_SOURCE_CANDIDATE = V2_RELEASE_CANDIDATE_VERSION
V2_STABLE_PROMOTION_POLICY = "same-qualified-implementation-version-metadata-only"


def _package_version() -> str:
    try:
        return version("pyworkflowkit")
    except PackageNotFoundError:  # pragma: no cover - source-tree fallback
        return "0.0.0+unknown"


def v2_stable_release_evidence_manifest() -> dict[str, object]:
    """Return the deterministic LOT-23 stable-promotion evidence manifest."""

    rc = v2_release_candidate_evidence_manifest()
    payload = {
        "contract_version": V2_STABLE_CONTRACT_VERSION,
        "stable_version": V2_STABLE_VERSION,
        "source_candidate": V2_STABLE_SOURCE_CANDIDATE,
        "package_version": _package_version(),
        "promotion_policy": V2_STABLE_PROMOTION_POLICY,
        "architecture_redesign_permitted": False,
        "new_runtime_capability_permitted": False,
        "supported_python_versions": list(V2_SUPPORTED_PYTHON_VERSIONS),
        "stable_identities": list(V2_STABLE_IDENTITIES),
        "stable_protocols": {
            key: list(value) for key, value in sorted(V2_STABLE_PROTOCOLS.items())
        },
        "required_qualification_families": list(V2_RC_REQUIRED_QUALIFICATION_FAMILIES),
        "root_api": v2_root_public_api_snapshot(),
        "states": v2_state_contract_snapshot(),
        "wire": v2_boundary_wire_contract_snapshot(),
        "executor": v2_executor_contract_snapshot(),
        "metadata_store": v2_metadata_store_contract_snapshot(),
        "sibling_integrations": {
            "pyingestkit": v2_pyingestkit_integration_snapshot(),
            "pytransformkit": v2_pytransformkit_integration_snapshot(),
        },
        "migration": {
            "head_revision": MIGRATION_HEAD_REVISION,
            "contract": migration_contract_snapshot(),
        },
        "rc_contract_versions": {
            name: value["contract_version"]
            for name, value in sorted(rc["contracts"].items())
            if isinstance(value, dict) and "contract_version" in value
        },
    }
    encoded = json.dumps(payload, allow_nan=False, sort_keys=True)
    return cast(dict[str, object], json.loads(encoded))


__all__ = [
    "V2_STABLE_CONTRACT_VERSION",
    "V2_STABLE_PROMOTION_POLICY",
    "V2_STABLE_SOURCE_CANDIDATE",
    "V2_STABLE_VERSION",
    "v2_stable_release_evidence_manifest",
]
