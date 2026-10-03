"""Qualify any installed PyWorkflowKit artifact against the frozen 1.0 baseline."""

from __future__ import annotations

import argparse
import json
from importlib.metadata import version

from pyworkflowkit.compatibility import CompatibilityStatus, compatibility_contract_snapshot
from pyworkflowkit.contracts.release_candidate import (
    RELEASE_CANDIDATE_CONTRACT_VERSION,
    RELEASE_CANDIDATE_TARGET_RELEASE,
    RELEASE_CANDIDATE_VERSION,
    REQUIRED_QUALIFICATION_JOB_IDS,
    release_candidate_contract_snapshot,
)
from pyworkflowkit.release_contract import release_contract_snapshot


def qualify_release_candidate() -> dict[str, object]:
    installed_version = version("pyworkflowkit")
    release = release_contract_snapshot()
    candidate = release_candidate_contract_snapshot()
    compatibility = compatibility_contract_snapshot()

    assert release["package_version"] == installed_version
    assert release["contracts"]["release_candidate"] == RELEASE_CANDIDATE_CONTRACT_VERSION
    assert release["release_candidate"] == candidate

    assert candidate["target_release"] == RELEASE_CANDIDATE_TARGET_RELEASE
    tracks = candidate["stabilization_tracks"]
    assert isinstance(tracks, dict)
    assert tuple(sorted(tracks)) == ("RQ-01", "RQ-02", "RQ-03", "RQ-04", "RQ-05")

    for values in tracks.values():
        assert isinstance(values, dict)
        assert values["contract_version"] == "1"
        assert values["target_release"] == "1.0.0"

    by_status = compatibility["by_status"]
    assert isinstance(by_status, dict)
    assert by_status[CompatibilityStatus.DEPRECATED.value] == []
    assert by_status[CompatibilityStatus.REMOVE_BEFORE_1_0.value] == []

    assert candidate["required_qualification_jobs"] == list(REQUIRED_QUALIFICATION_JOB_IDS)
    assert candidate["promotion_policy"] == "same-qualified-code-version-metadata-only"

    return {
        "candidate_version": RELEASE_CANDIDATE_VERSION,
        "installed_version": installed_version,
        "baseline_target_release": RELEASE_CANDIDATE_TARGET_RELEASE,
        "stabilization_tracks": list(sorted(tracks)),
        "qualification_jobs": list(REQUIRED_QUALIFICATION_JOB_IDS),
        "compatibility_blockers": [],
        "promotion_policy": candidate["promotion_policy"],
        "technical_readiness": "qualified",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = qualify_release_candidate()
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print("RQ-06 1.0 compatibility baseline qualification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
