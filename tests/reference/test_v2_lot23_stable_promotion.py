"""LOT-23 PyWorkflowKit 2.0.0 stable-promotion acceptance."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pyworkflowkit
from pyworkflowkit._architecture import V2_ROOT_TARGET_ALLOWLIST
from pyworkflowkit.contracts.v2_release_candidate import (
    V2_RELEASE_CANDIDATE_VERSION,
    V2_STABLE_IDENTITIES,
    V2_STABLE_PROTOCOLS,
)
from pyworkflowkit.contracts.v2_stable import (
    V2_STABLE_CONTRACT_VERSION,
    V2_STABLE_PROMOTION_POLICY,
    V2_STABLE_SOURCE_CANDIDATE,
    V2_STABLE_VERSION,
    v2_stable_release_evidence_manifest,
)
from pyworkflowkit.migrations.contract import MIGRATION_HEAD_REVISION

ROOT = Path(__file__).resolve().parents[2]


def test_lot23_package_identity_and_classifier_are_stable() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["version"] == V2_STABLE_VERSION == "2.0.0"
    assert pyworkflowkit.__version__ == "2.0.0"
    assert "Development Status :: 5 - Production/Stable" in project["classifiers"]
    assert "Development Status :: 4 - Beta" not in project["classifiers"]


def test_lot23_promotes_exact_rc_contract_without_root_redesign() -> None:
    manifest = v2_stable_release_evidence_manifest()

    assert V2_STABLE_SOURCE_CANDIDATE == V2_RELEASE_CANDIDATE_VERSION == "2.0.0rc1"
    assert manifest["source_candidate"] == "2.0.0rc1"
    assert manifest["stable_version"] == "2.0.0"
    assert manifest["package_version"] == "2.0.0"
    assert manifest["promotion_policy"] == V2_STABLE_PROMOTION_POLICY
    assert V2_STABLE_PROMOTION_POLICY == "same-qualified-implementation-version-metadata-only"
    assert manifest["architecture_redesign_permitted"] is False
    assert manifest["new_runtime_capability_permitted"] is False
    assert tuple(pyworkflowkit.__all__) == V2_ROOT_TARGET_ALLOWLIST
    assert manifest["root_api"]["exports"] == list(V2_ROOT_TARGET_ALLOWLIST)


def test_lot23_freezes_states_identities_protocols_and_wire_contracts() -> None:
    manifest = v2_stable_release_evidence_manifest()

    assert manifest["stable_identities"] == list(V2_STABLE_IDENTITIES)
    assert set(manifest["stable_protocols"]) == set(V2_STABLE_PROTOCOLS)
    assert manifest["states"]["contract_version"] == "1"
    assert manifest["executor"]["contract_version"] == "4"
    assert manifest["metadata_store"]["contract_version"] == "2"
    assert manifest["wire"]["contract_family_version"] == "1"
    assert manifest["wire"]["codec_contract_version"] == "1"
    assert manifest["wire"]["non_executable_deserialization"] is True


def test_lot23_sibling_integrations_remain_optional_opaque_and_versioned() -> None:
    siblings = v2_stable_release_evidence_manifest()["sibling_integrations"]
    assert isinstance(siblings, dict)

    pyingestkit = siblings["pyingestkit"]
    pytransformkit = siblings["pytransformkit"]

    assert pyingestkit["contract_version"] == "1"
    assert pyingestkit["imports_pyingestkit"] is False
    assert pyingestkit["raw_credentials_supported"] is False
    assert pyingestkit["unknown_outcome_requires_reconciliation"] is True

    assert pytransformkit["contract_version"] == "1"
    assert pytransformkit["imports_pytransformkit"] is False
    assert pytransformkit["raw_credentials_supported"] is False
    assert pytransformkit["unknown_outcome_requires_reconciliation"] is True


def test_lot23_migration_contract_and_head_are_finalized() -> None:
    migration = v2_stable_release_evidence_manifest()["migration"]
    assert isinstance(migration, dict)

    assert MIGRATION_HEAD_REVISION == "0005_v2_task_output_checkpoints"
    assert migration["head_revision"] == MIGRATION_HEAD_REVISION
    assert migration["contract"]["direction"] == "v1_to_v2_only"
    assert migration["contract"]["generic_aliases_preserved"] is False
    assert migration["contract"]["retry_history_requires_contiguous_attempt_numbers"] is True


def test_lot23_stable_manifest_is_deterministic_json() -> None:
    first = v2_stable_release_evidence_manifest()
    second = v2_stable_release_evidence_manifest()

    assert V2_STABLE_CONTRACT_VERSION == "1"
    assert first == second
    encoded = json.dumps(first, allow_nan=False, sort_keys=True)
    assert json.loads(encoded) == first


def test_lot23_release_metadata_and_migration_guide_are_present() -> None:
    stable_note = ROOT / "docs" / "releases" / "2.0.0.md"
    rc_note = ROOT / "docs" / "releases" / "2.0.0rc1.md"
    migration_guide = ROOT / "docs" / "migration" / "V1_TO_V2.md"
    qualification_report = ROOT / "docs" / "releases" / "2.0.0_QUALIFICATION_REPORT.md"

    assert stable_note.is_file()
    assert rc_note.is_file()
    assert migration_guide.is_file()
    assert qualification_report.is_file()
    assert stable_note.read_text(encoding="utf-8").splitlines()[0] == "# PyWorkflowKit 2.0.0"

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 2.0.0 - 2026-10-03" in changelog
    assert "## 2.0.0rc1 - 2026-10-03" in changelog
