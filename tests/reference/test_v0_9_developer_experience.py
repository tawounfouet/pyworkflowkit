"""RQ-04 acceptance for developer experience and documentation."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from pyworkflowkit.compatibility import COMPATIBILITY_SUBJECTS, CompatibilityStatus
from pyworkflowkit.contracts.developer_experience import (
    CLI_FIRST_RUN_COMMANDS,
    DX_CONTRACT_VERSION,
    DX_TARGET_RELEASE,
    EXECUTABLE_EXAMPLES,
    GETTING_STARTED_GUIDES,
    PUBLIC_AUTHORING_FACADES,
    developer_experience_contract_snapshot,
)
from pyworkflowkit.release_contract import REQUIRED_CONTRACT_VERSIONS, release_contract_snapshot

ROOT = Path(__file__).resolve().parents[2]


def test_rq04_contract_targets_1_0() -> None:
    assert DX_CONTRACT_VERSION == "1"
    assert DX_TARGET_RELEASE == "1.0.0"
    assert PUBLIC_AUTHORING_FACADES == (
        "pyworkflowkit",
        "pyworkflowkit.ecosystem",
    )
    assert CLI_FIRST_RUN_COMMANDS == (
        "version",
        "validate",
        "plan",
        "run",
        "inspect",
        "events",
        "manifest",
    )


def test_rq04_guides_and_examples_exist() -> None:
    for relative_path in (*GETTING_STARTED_GUIDES, *EXECUTABLE_EXAMPLES):
        assert (ROOT / relative_path).is_file(), relative_path


def test_rq04_examples_use_only_documented_authoring_facades() -> None:
    allowed = set(PUBLIC_AUTHORING_FACADES)

    for relative_path in EXECUTABLE_EXAMPLES:
        tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
        imported: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported.add(node.module)

        pyworkflowkit_imports = {
            name
            for name in imported
            if name == "pyworkflowkit" or name.startswith("pyworkflowkit.")
        }
        assert pyworkflowkit_imports <= allowed, (
            relative_path,
            sorted(pyworkflowkit_imports - allowed),
        )


def test_rq04_readme_points_to_getting_started_path() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/guides/getting-started.md" in readme
    assert "examples/00_hello_world.py" in readme
    assert "pyworkflow validate" in readme


def test_rq04_is_stable_compatibility_evidence() -> None:
    matching = [
        subject
        for subject in COMPATIBILITY_SUBJECTS
        if subject.key == "developer_experience.first_use"
    ]

    assert len(matching) == 1
    assert matching[0].status is CompatibilityStatus.STABLE
    assert matching[0].contract_version == "1"


def test_rq04_snapshot_is_json_portable_and_part_of_release_contract() -> None:
    snapshot = developer_experience_contract_snapshot()
    encoded = json.dumps(snapshot, allow_nan=False, sort_keys=True)

    assert json.loads(encoded) == snapshot
    assert dict(REQUIRED_CONTRACT_VERSIONS)["developer_experience"] == "1"

    release_snapshot = release_contract_snapshot()
    assert release_snapshot["contracts"]["developer_experience"] == "1"
    assert release_snapshot["developer_experience"] == snapshot
