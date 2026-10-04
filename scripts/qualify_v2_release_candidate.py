#!/usr/bin/env python3
"""Installed-artifact PyWorkflowKit 2.0 release-candidate qualification."""

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


def main() -> None:
    manifest = v2_release_candidate_evidence_manifest()

    assert pyworkflowkit.__version__ in {
        V2_RELEASE_CANDIDATE_VERSION,
        V2_RELEASE_CANDIDATE_TARGET_RELEASE,
        "2.1.0rc1",
        "2.1.0",
        "2.1.1",
    }
    assert manifest["package_version"] == pyworkflowkit.__version__
    assert manifest["candidate_version"] == V2_RELEASE_CANDIDATE_VERSION
    assert manifest["target_release"] == V2_RELEASE_CANDIDATE_TARGET_RELEASE
    assert tuple(pyworkflowkit.__all__) == V2_ROOT_TARGET_ALLOWLIST
    assert manifest["contracts"]["root_api"]["exports"] == list(V2_ROOT_TARGET_ALLOWLIST)
    assert manifest["change_policy"] == V2_RC_CHANGE_POLICY
    assert manifest["architecture_redesign_permitted"] is False

    payload = {
        "contract": "pyworkflowkit.v2_release_candidate",
        "contract_version": manifest["contract_version"],
        "candidate_version": manifest["candidate_version"],
        "target_release": manifest["target_release"],
        "root_exports": manifest["contracts"]["root_api"]["exports"],
        "stable_identities": manifest["stable_identities"],
        "qualification_family_count": len(manifest["required_qualification_families"]),
        "contract_names": sorted(manifest["contracts"]),
        "change_policy": manifest["change_policy"],
    }
    print(json.dumps(payload, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
