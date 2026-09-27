"""RQ-06 acceptance for the PyWorkflowKit 1.0 release candidate."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from pyworkflowkit.compatibility import COMPATIBILITY_SUBJECTS, CompatibilityStatus
from pyworkflowkit.contracts.release_candidate import (
    MANUAL_1_0_PUBLICATION_DECISIONS,
    PROMOTION_POLICY,
    RELEASE_CANDIDATE_CONTRACT_VERSION,
    RELEASE_CANDIDATE_TARGET_RELEASE,
    RELEASE_CANDIDATE_VERSION,
    REQUIRED_QUALIFICATION_JOB_IDS,
    STABILIZATION_TRACKS,
    release_candidate_contract_snapshot,
)
from pyworkflowkit.release_contract import REQUIRED_CONTRACT_VERSIONS, release_contract_snapshot

ROOT = Path(__file__).resolve().parents[2]


def test_rq06_candidate_identity_and_target_are_frozen() -> None:
    assert RELEASE_CANDIDATE_CONTRACT_VERSION == "1"
    assert RELEASE_CANDIDATE_VERSION == "0.9.0rc2"
    assert RELEASE_CANDIDATE_TARGET_RELEASE == "1.0.0"
    assert PROMOTION_POLICY == "same-qualified-code-version-metadata-only"


def test_rq06_inherits_all_stabilization_tracks() -> None:
    assert tuple(STABILIZATION_TRACKS) == (
        "RQ-01",
        "RQ-02",
        "RQ-03",
        "RQ-04",
        "RQ-05",
    )

    for track in STABILIZATION_TRACKS.values():
        assert track["contract_version"] == "1"
        assert track["target_release"] == "1.0.0"


def test_rq06_has_no_compatibility_blockers() -> None:
    blockers = [
        subject.key
        for subject in COMPATIBILITY_SUBJECTS
        if subject.status
        in {
            CompatibilityStatus.DEPRECATED,
            CompatibilityStatus.REMOVE_BEFORE_1_0,
        }
    ]

    assert blockers == []


def test_rq06_requires_every_inherited_release_qualification_family() -> None:
    assert REQUIRED_QUALIFICATION_JOB_IDS == (
        "artifact-install",
        "public-api-freeze",
        "compatibility-deprecation",
        "static-typing",
        "developer-experience",
        "packaging-distribution",
        "reference-contracts",
        "reference-integrations",
        "control-plane-provider",
        "ecosystem-sdk",
        "transverse-v0-8",
        "sqlite-upgrade",
        "postgres-upgrade",
        "security",
    )

    workflow = (ROOT / ".github/workflows/release-qualification.yml").read_text(encoding="utf-8")

    assert "release-candidate:" in workflow
    for job_id in REQUIRED_QUALIFICATION_JOB_IDS:
        assert f"      - {job_id}\n" in workflow


def test_rq06_release_metadata_is_candidate_consistent() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == RELEASE_CANDIDATE_VERSION

    note = ROOT / "docs" / "releases" / f"{RELEASE_CANDIDATE_VERSION}.md"
    assert note.is_file()
    assert note.read_text(encoding="utf-8").splitlines()[0] == (
        f"# PyWorkflowKit {RELEASE_CANDIDATE_VERSION}"
    )

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert RELEASE_CANDIDATE_VERSION in changelog


def test_rq06_release_contract_composes_candidate_contract() -> None:
    assert dict(REQUIRED_CONTRACT_VERSIONS)["release_candidate"] == "1"

    snapshot = release_contract_snapshot()

    assert snapshot["package_version"] == RELEASE_CANDIDATE_VERSION
    assert snapshot["contracts"]["release_candidate"] == "1"
    assert snapshot["release_candidate"] == release_candidate_contract_snapshot()


def test_rq06_snapshot_is_json_portable() -> None:
    snapshot = release_candidate_contract_snapshot()
    encoded = json.dumps(snapshot, allow_nan=False, sort_keys=True)

    assert json.loads(encoded) == snapshot


def test_rq06_license_remains_explicit_manual_publication_decision() -> None:
    assert MANUAL_1_0_PUBLICATION_DECISIONS == ("software_license",)
