#!/usr/bin/env python3
"""Installed-artifact PyWorkflowKit 2.1 release-candidate qualification (LOT-37)."""

from __future__ import annotations

import json
from pathlib import Path

import pyworkflowkit
from pyworkflowkit._architecture import V2_ROOT_TARGET_ALLOWLIST
from pyworkflowkit.cli.public_contract import (
    active_cli_command_names,
    verify_cli_contract_parity,
)
from pyworkflowkit.cli_contract import CLI_COMMANDS

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_VERSION = "2.1.0rc1"
TARGET_RELEASE = "2.1.0"


def main() -> None:
    # 1. Version and root API parity
    assert pyworkflowkit.__version__ in {CANDIDATE_VERSION, TARGET_RELEASE}, (
        f"Unexpected version: {pyworkflowkit.__version__}"
    )
    assert tuple(pyworkflowkit.__all__) == V2_ROOT_TARGET_ALLOWLIST, (
        "Root exports must strictly match canonical V2 allowlist"
    )

    # 2. CLI Contract Freeze Parity
    assert active_cli_command_names() == set(CLI_COMMANDS)
    assert verify_cli_contract_parity() is True

    # 3. Customer 360 v2 Reference Example verification
    example_path = ROOT / "docs" / "examples" / "customer_360_v2.py"
    assert example_path.is_file(), f"Missing canonical example at {example_path}"

    # 4. Release notes and changelog
    release_note = ROOT / "docs" / "releases" / f"{CANDIDATE_VERSION}.md"
    assert release_note.is_file(), f"Missing release note: {release_note}"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## {CANDIDATE_VERSION}" in changelog

    payload = {
        "contract": "pyworkflowkit.v2_1_release_candidate",
        "candidate_version": CANDIDATE_VERSION,
        "target_release": TARGET_RELEASE,
        "package_version": pyworkflowkit.__version__,
        "cli_commands_count": len(CLI_COMMANDS),
        "cli_parity_verified": True,
        "canonical_example_present": True,
        "release_notes_verified": True,
    }
    print(json.dumps(payload, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
