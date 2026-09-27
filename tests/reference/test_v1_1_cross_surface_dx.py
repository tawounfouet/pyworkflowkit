"""DX06 acceptance for the PyWorkflowKit 1.1 cross-surface Developer Experience."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote

from pyworkflowkit.contracts.developer_experience import (
    DX_CONTRACT_VERSION,
    DX_TARGET_RELEASE,
    DX_V2_CANONICAL_EXAMPLES,
    DX_V2_CANONICAL_GUIDES,
    DX_V2_CANONICAL_NOTEBOOKS,
    DX_V2_CLI_COMMANDS,
    DX_V2_CONTRACT_VERSION,
    DX_V2_CROSS_SURFACE_CONCEPTS,
    DX_V2_PUBLIC_AUTHORING_FACADES,
    DX_V2_REQUIRED_SURFACES,
    DX_V2_TARGET_RELEASE,
    developer_experience_contract_snapshot,
    developer_experience_contract_snapshot_v2,
)

ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_LINK = re.compile(r"\]\(([^)]+)\)")

STALE_LEARNING_MARKERS = (
    "DX04 target",
    "DX05 target",
    "DX05 will provide",
    "Planned in DX03",
)


def _current_learning_markdown() -> tuple[Path, ...]:
    guides = tuple(ROOT.joinpath("docs", "guides").glob("*.md"))
    return (
        ROOT / "README.md",
        ROOT / "examples" / "README.md",
        ROOT / "notebooks" / "README.md",
        *guides,
    )


def _relative_link_target(source: Path, raw_target: str) -> Path | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    if target.startswith(("http://", "https://", "mailto:", "#")):
        return None

    target = target.split("#", 1)[0].split("?", 1)[0].strip()
    if not target:
        return None
    return (source.parent / unquote(target)).resolve()


def test_dx06_preserves_dx_contract_v1_and_adds_v2() -> None:
    assert DX_CONTRACT_VERSION == "1"
    assert DX_TARGET_RELEASE == "1.0.0"
    assert developer_experience_contract_snapshot()["contract_version"] == "1"

    assert DX_V2_CONTRACT_VERSION == "2"
    assert DX_V2_TARGET_RELEASE == "1.1.0"
    assert DX_V2_REQUIRED_SURFACES == (
        "cli",
        "guides",
        "examples",
        "notebooks",
        "tests",
    )
    assert DX_V2_PUBLIC_AUTHORING_FACADES == (
        "pyworkflowkit",
        "pyworkflowkit.ecosystem",
        "pyworkflowkit.control_plane",
        "pyworkflowkit.integrations",
    )


def test_dx06_v2_snapshot_is_json_portable_and_complete() -> None:
    snapshot = developer_experience_contract_snapshot_v2()
    encoded = json.dumps(snapshot, allow_nan=False, sort_keys=True)

    assert json.loads(encoded) == snapshot
    assert snapshot["contract_version"] == "2"
    assert snapshot["target_release"] == "1.1.0"
    assert len(DX_V2_CANONICAL_GUIDES) == 29
    assert len(DX_V2_CANONICAL_EXAMPLES) == 24
    assert len(DX_V2_CANONICAL_NOTEBOOKS) == 19
    assert len(DX_V2_CROSS_SURFACE_CONCEPTS) == 18
    assert DX_V2_CLI_COMMANDS == (
        "version",
        "validate",
        "plan",
        "run",
        "inspect",
        "events",
        "manifest",
        "plugins",
        "doctor",
    )


def test_dx06_every_contract_artifact_exists() -> None:
    for relative_path in (
        *DX_V2_CANONICAL_GUIDES,
        *DX_V2_CANONICAL_EXAMPLES,
        *DX_V2_CANONICAL_NOTEBOOKS,
    ):
        assert (ROOT / relative_path).is_file(), relative_path


def test_dx06_cross_surface_concepts_are_bidirectionally_linked() -> None:
    for concept, guide_path, example_path, notebook_path in DX_V2_CROSS_SURFACE_CONCEPTS:
        guide = (ROOT / guide_path).read_text(encoding="utf-8")
        notebook = (ROOT / notebook_path).read_text(encoding="utf-8")

        assert example_path in guide, f"{concept}: guide -> example"
        assert Path(notebook_path).name in guide, f"{concept}: guide -> notebook"
        assert f"../{guide_path}" in notebook, f"{concept}: notebook -> guide"
        assert f"../{example_path}" in notebook, f"{concept}: notebook -> example"


def test_dx06_current_learning_markdown_links_resolve() -> None:
    for source in _current_learning_markdown():
        content = source.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(content):
            target = _relative_link_target(source, match.group(1))
            if target is not None:
                assert target.exists(), f"{source.relative_to(ROOT)} -> {match.group(1)}"


def test_dx06_current_learning_surfaces_have_no_stale_lot_placeholders() -> None:
    for source in _current_learning_markdown():
        content = source.read_text(encoding="utf-8")
        for marker in STALE_LEARNING_MARKERS:
            assert marker not in content, f"{source.relative_to(ROOT)}: {marker}"


def test_dx06_readme_exposes_all_three_learning_entry_points() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/guides/README.md" in readme
    assert "examples/README.md" in readme
    assert "notebooks/README.md" in readme
    assert "pwk" in readme
