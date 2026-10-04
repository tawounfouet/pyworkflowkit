#!/usr/bin/env python3
"""Installed-artifact PyWorkflowKit 2.0.0 stable-promotion qualification."""

from __future__ import annotations

import json

import pyworkflowkit
from pyworkflowkit._architecture import V2_ROOT_TARGET_ALLOWLIST
from pyworkflowkit.contracts.v2_release_candidate import (
    V2_RC_CHANGE_POLICY,
    V2_RELEASE_CANDIDATE_TARGET_RELEASE,
    V2_RELEASE_CANDIDATE_VERSION,
    v2_release_candidate_evidence_manifest,
)
from pyworkflowkit.migrations.contract import MIGRATION_HEAD_REVISION

STABLE_VERSION = "2.0.0"
ALLOWED_VERSIONS = {STABLE_VERSION, "2.1.0rc1", "2.1.0"}


def main() -> None:
    manifest = v2_release_candidate_evidence_manifest()
    contracts = manifest["contracts"]
    assert isinstance(contracts, dict)

    assert pyworkflowkit.__version__ in ALLOWED_VERSIONS
    assert tuple(pyworkflowkit.__all__) == V2_ROOT_TARGET_ALLOWLIST
    assert V2_RELEASE_CANDIDATE_VERSION == "2.0.0rc1"
    assert V2_RELEASE_CANDIDATE_TARGET_RELEASE == STABLE_VERSION
    assert manifest["candidate_version"] == V2_RELEASE_CANDIDATE_VERSION
    assert manifest["target_release"] == STABLE_VERSION
    assert manifest["package_version"] in ALLOWED_VERSIONS
    assert contracts["root_api"]["exports"] == list(V2_ROOT_TARGET_ALLOWLIST)
    assert contracts["states"]["contract_version"] == "1"
    assert contracts["executor"]["contract_version"] == "4"
    assert contracts["metadata_store"]["contract_version"] == "2"
    assert contracts["wire"]["contract_family_version"] == "1"
    assert contracts["plugins"]["plugin_api_version"] == "2"
    assert contracts["migration"]["direction"] == "v1_to_v2_only"
    assert contracts["pyingestkit"]["imports_pyingestkit"] is False
    assert contracts["pytransformkit"]["imports_pytransformkit"] is False
    assert manifest["change_policy"] == V2_RC_CHANGE_POLICY
    assert manifest["architecture_redesign_permitted"] is False
    assert MIGRATION_HEAD_REVISION == "0005_v2_task_output_checkpoints"

    payload = {
        "contract": "pyworkflowkit.v2_stable_promotion",
        "version": pyworkflowkit.__version__,
        "source_candidate": V2_RELEASE_CANDIDATE_VERSION,
        "root_exports": contracts["root_api"]["exports"],
        "stable_identities": manifest["stable_identities"],
        "migration_head": MIGRATION_HEAD_REVISION,
        "contract_names": sorted(contracts),
        "change_policy": manifest["change_policy"],
    }
    print(json.dumps(payload, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
