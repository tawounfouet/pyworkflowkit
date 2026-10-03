#!/usr/bin/env python3
"""Installed-artifact PyWorkflowKit 2.0.0 stable-promotion qualification."""

from __future__ import annotations

import json

import pyworkflowkit
from pyworkflowkit._architecture import V2_ROOT_TARGET_ALLOWLIST
from pyworkflowkit.contracts.v2_release_candidate import V2_RELEASE_CANDIDATE_VERSION
from pyworkflowkit.contracts.v2_stable import (
    V2_STABLE_PROMOTION_POLICY,
    V2_STABLE_SOURCE_CANDIDATE,
    V2_STABLE_VERSION,
    v2_stable_release_evidence_manifest,
)


def main() -> None:
    manifest = v2_stable_release_evidence_manifest()

    assert pyworkflowkit.__version__ == V2_STABLE_VERSION == "2.0.0"
    assert manifest["package_version"] == V2_STABLE_VERSION
    assert manifest["stable_version"] == V2_STABLE_VERSION
    assert manifest["source_candidate"] == V2_STABLE_SOURCE_CANDIDATE
    assert V2_STABLE_SOURCE_CANDIDATE == V2_RELEASE_CANDIDATE_VERSION
    assert tuple(pyworkflowkit.__all__) == V2_ROOT_TARGET_ALLOWLIST
    assert manifest["root_api"]["exports"] == list(V2_ROOT_TARGET_ALLOWLIST)
    assert manifest["promotion_policy"] == V2_STABLE_PROMOTION_POLICY
    assert manifest["architecture_redesign_permitted"] is False
    assert manifest["new_runtime_capability_permitted"] is False
    assert manifest["migration"]["head_revision"] == "0005_v2_task_output_checkpoints"
    assert manifest["sibling_integrations"]["pyingestkit"]["imports_pyingestkit"] is False
    assert manifest["sibling_integrations"]["pytransformkit"]["imports_pytransformkit"] is False

    payload = {
        "contract": "pyworkflowkit.v2_stable",
        "contract_version": manifest["contract_version"],
        "stable_version": manifest["stable_version"],
        "source_candidate": manifest["source_candidate"],
        "root_exports": manifest["root_api"]["exports"],
        "stable_identities": manifest["stable_identities"],
        "qualification_family_count": len(manifest["required_qualification_families"]),
        "migration_head": manifest["migration"]["head_revision"],
        "promotion_policy": manifest["promotion_policy"],
    }
    print(json.dumps(payload, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
