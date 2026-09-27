"""M46 reference acceptance for release qualification contracts."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pyworkflowkit.release_contract import (
    RELEASE_QUALIFICATION_CONTRACT_VERSION,
    REQUIRED_CONTRACT_VERSIONS,
    SUPPORTED_PYTHON_VERSIONS,
    release_contract_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]


def test_m46_release_qualification_contract_is_frozen() -> None:
    assert RELEASE_QUALIFICATION_CONTRACT_VERSION == "1"
    assert SUPPORTED_PYTHON_VERSIONS == ("3.11", "3.12", "3.13")
    assert dict(REQUIRED_CONTRACT_VERSIONS) == {
        "cli_machine": "1",
        "manifest": "1",
        "persistence": "1",
        "plugin_api": "1",
    }


def test_m46_snapshot_assembles_m41_to_m45_contracts() -> None:
    snapshot = release_contract_snapshot()

    assert snapshot["qualification_contract_version"] == "1"
    assert snapshot["supported_python_versions"] == ["3.11", "3.12", "3.13"]
    assert snapshot["contracts"] == {
        "cli_machine": "1",
        "manifest": "1",
        "persistence": "1",
        "plugin_api": "1",
    }
    assert snapshot["migration_head"] == "0003_retry_eligible_at"


def test_m46_current_version_has_release_note_and_changelog_gate() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(project["project"]["version"])
    release_note = ROOT / "docs" / "releases" / f"{version}.md"

    assert release_note.is_file()
    assert release_note.read_text(encoding="utf-8").splitlines()[0] == (
        f"# PyWorkflowKit {version}"
    )
    assert version in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
