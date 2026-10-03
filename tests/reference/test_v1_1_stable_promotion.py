"""Stable-promotion acceptance for PyWorkflowKit 1.1.0."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pyworkflowkit.contracts.developer_experience import (
    DX_CONTRACT_VERSION,
    DX_TARGET_RELEASE,
    DX_V2_CONTRACT_VERSION,
    DX_V2_TARGET_RELEASE,
    developer_experience_contract_snapshot_v2,
)

ROOT = Path(__file__).resolve().parents[2]


def test_v1_1_stable_promotion_remains_historical_evidence_on_v2_stable() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["version"] == "2.0.0"
    assert "Development Status :: 5 - Production/Stable" in project["classifiers"]
    assert (ROOT / "docs" / "releases" / "1.1.0.md").is_file()


def test_v1_1_stable_preserves_dx_contract_lineage() -> None:
    assert DX_CONTRACT_VERSION == "1"
    assert DX_TARGET_RELEASE == "1.0.0"
    assert DX_V2_CONTRACT_VERSION == "2"
    assert DX_V2_TARGET_RELEASE == "1.1.0"

    snapshot = developer_experience_contract_snapshot_v2()
    assert snapshot["contract_version"] == "2"
    assert snapshot["target_release"] == "1.1.0"


def test_v1_1_stable_release_metadata_is_present() -> None:
    rc_note = ROOT / "docs" / "releases" / "1.1.0rc1.md"
    stable_note = ROOT / "docs" / "releases" / "1.1.0.md"

    assert rc_note.is_file()
    assert stable_note.is_file()
    assert stable_note.read_text(encoding="utf-8").splitlines()[0] == "# PyWorkflowKit 1.1.0"

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 1.1.0 - 2026-09-28" in changelog
    assert "## 1.1.0rc1 - 2026-09-28" in changelog


def test_v1_1_roadmap_is_closed() -> None:
    roadmap_path = ROOT / "docs" / "V1_1_DEVELOPER_EXPERIENCE_AND_LEARNING_ROADMAP.md"
    roadmap = roadmap_path.read_text(encoding="utf-8")

    assert "| DX06 | 1.1.0rc1 | Transverse DX qualification | Complete |" in roadmap
    assert "| Stable | 1.1.0 | Developer Experience & Learning | Complete |" in roadmap
    assert "same qualified implementation" not in roadmap.lower()
