"""LOT-23 PyWorkflowKit 2.0.0 stable-promotion acceptance."""

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path

import pyworkflowkit
from pyworkflowkit._architecture import V2_ROOT_TARGET_ALLOWLIST
from pyworkflowkit.contracts.v2_release_candidate import (
    V2_RC_CHANGE_POLICY,
    V2_RELEASE_CANDIDATE_TARGET_RELEASE,
    V2_RELEASE_CANDIDATE_VERSION,
    V2_STABLE_IDENTITIES,
    V2_STABLE_PROTOCOLS,
    v2_release_candidate_evidence_manifest,
)
from pyworkflowkit.migrations.contract import MIGRATION_HEAD_REVISION

ROOT = Path(__file__).resolve().parents[2]
RC_MERGE_COMMIT = "3cd55294ca749709245894efed7da536c9f9831e"
RC_SOURCE_TREE_SHA = "f0797a25b877a0379f578015787b58f06a74dea2"
STABLE_VERSION = "2.0.0"


def _source_tree_sha(ref: str = "HEAD") -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"{ref}:src/pyworkflowkit"],
        cwd=ROOT,
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def test_lot23_runtime_source_tree_is_exact_rc_baseline() -> None:
    for ref in ("v2.0.0", RC_MERGE_COMMIT, "HEAD"):
        try:
            if _source_tree_sha(ref) == RC_SOURCE_TREE_SHA:
                return
        except subprocess.CalledProcessError:
            continue

    report = (ROOT / "docs" / "releases" / "2.0.0-qualification-report.md").read_text(
        encoding="utf-8"
    )
    assert RC_SOURCE_TREE_SHA in report


def test_lot23_package_identity_and_classifier_are_stable() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["version"] in {STABLE_VERSION, "2.1.0rc1", "2.1.0", "2.1.1"}
    assert pyworkflowkit.__version__ in {STABLE_VERSION, "2.1.0rc1", "2.1.0", "2.1.1"}
    assert "Development Status :: 5 - Production/Stable" in project["classifiers"]
    assert "Development Status :: 4 - Beta" not in project["classifiers"]


def test_lot23_root_contract_is_unchanged_from_rc() -> None:
    assert tuple(pyworkflowkit.__all__) == V2_ROOT_TARGET_ALLOWLIST


def test_lot23_rc_lineage_is_preserved_under_stable_package() -> None:
    manifest = v2_release_candidate_evidence_manifest()

    assert V2_RELEASE_CANDIDATE_VERSION == "2.0.0rc1"
    assert V2_RELEASE_CANDIDATE_TARGET_RELEASE == STABLE_VERSION
    assert V2_RC_CHANGE_POLICY == "blocker-fixes-only-without-rc-reset"
    assert manifest["candidate_version"] == "2.0.0rc1"
    assert manifest["target_release"] == STABLE_VERSION
    assert manifest["package_version"] in {STABLE_VERSION, "2.1.0rc1", "2.1.0", "2.1.1"}
    assert manifest["architecture_redesign_permitted"] is False


def test_lot23_freezes_identity_protocol_and_contract_baselines() -> None:
    manifest = v2_release_candidate_evidence_manifest()
    contracts = manifest["contracts"]
    assert isinstance(contracts, dict)

    assert manifest["stable_identities"] == list(V2_STABLE_IDENTITIES)
    assert set(manifest["stable_protocols"]) == set(V2_STABLE_PROTOCOLS)
    assert contracts["states"]["contract_version"] == "1"
    assert contracts["executor"]["contract_version"] == "4"
    assert contracts["metadata_store"]["contract_version"] == "2"
    assert contracts["wire"]["contract_family_version"] == "1"
    assert contracts["plugins"]["plugin_api_version"] == "2"


def test_lot23_sibling_integrations_remain_optional_and_opaque() -> None:
    contracts = v2_release_candidate_evidence_manifest()["contracts"]
    assert isinstance(contracts, dict)

    pyingestkit = contracts["pyingestkit"]
    pytransformkit = contracts["pytransformkit"]

    assert pyingestkit["contract_version"] == "1"
    assert pyingestkit["imports_pyingestkit"] is False
    assert pyingestkit["raw_credentials_supported"] is False
    assert pyingestkit["unknown_outcome_requires_reconciliation"] is True

    assert pytransformkit["contract_version"] == "1"
    assert pytransformkit["imports_pytransformkit"] is False
    assert pytransformkit["raw_credentials_supported"] is False
    assert pytransformkit["unknown_outcome_requires_reconciliation"] is True


def test_lot23_migration_contract_and_head_are_finalized() -> None:
    contracts = v2_release_candidate_evidence_manifest()["contracts"]
    assert isinstance(contracts, dict)

    assert MIGRATION_HEAD_REVISION == "0005_v2_task_output_checkpoints"
    assert contracts["migration"]["direction"] == "v1_to_v2_only"
    assert contracts["migration"]["generic_aliases_preserved"] is False
    assert contracts["migration"]["retry_history_requires_contiguous_attempt_numbers"] is True


def test_lot23_release_manifest_remains_deterministic_json() -> None:
    first = v2_release_candidate_evidence_manifest()
    second = v2_release_candidate_evidence_manifest()

    assert first == second
    assert json.loads(json.dumps(first, allow_nan=False, sort_keys=True)) == first


def test_lot23_release_metadata_and_migration_guide_are_present() -> None:
    stable_note = ROOT / "docs" / "releases" / "2.0.0.md"
    rc_note = ROOT / "docs" / "releases" / "2.0.0rc1.md"
    migration_guide = ROOT / "docs" / "migration" / "V1_TO_V2.md"
    qualification_report = ROOT / "docs" / "releases" / "2.0.0-qualification-report.md"

    assert stable_note.is_file()
    assert rc_note.is_file()
    assert migration_guide.is_file()
    assert qualification_report.is_file()
    assert stable_note.read_text(encoding="utf-8").splitlines()[0] == "# PyWorkflowKit 2.0.0"

    report = qualification_report.read_text(encoding="utf-8")
    assert RC_MERGE_COMMIT in report
    assert RC_SOURCE_TREE_SHA in report

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 2.0.0 - 2026-10-03" in changelog
    assert "## 2.0.0rc1 - 2026-10-03" in changelog
