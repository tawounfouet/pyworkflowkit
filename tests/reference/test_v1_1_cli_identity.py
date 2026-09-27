"""DX01 acceptance for canonical CLI identity and compatibility aliases."""

from __future__ import annotations

import tomllib
from importlib.metadata import entry_points
from pathlib import Path

from pyworkflowkit.compatibility import CONSOLE_SCRIPT_ALIASES
from pyworkflowkit.contracts.distribution import CONSOLE_SCRIPTS

ROOT = Path(__file__).resolve().parents[2]

EXPECTED_SCRIPTS = {
    "pwk": "pyworkflowkit.cli:main",
    "pyworkflow": "pyworkflowkit.cli:main",
    "pyworkflowkit": "pyworkflowkit.cli:main",
}


def test_dx01_project_metadata_exposes_canonical_pwk_and_compatibility_aliases() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["scripts"] == EXPECTED_SCRIPTS


def test_dx01_compatibility_and_distribution_contracts_agree() -> None:
    assert dict(CONSOLE_SCRIPT_ALIASES) == EXPECTED_SCRIPTS
    assert dict(CONSOLE_SCRIPTS) == EXPECTED_SCRIPTS


def test_dx01_installed_console_scripts_resolve_to_one_application() -> None:
    installed = {
        ep.name: ep.value
        for ep in entry_points(group="console_scripts")
        if ep.name in EXPECTED_SCRIPTS
    }

    assert installed == EXPECTED_SCRIPTS
