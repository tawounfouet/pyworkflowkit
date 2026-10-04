"""Release-documentation drift guards introduced by the 2.1 post-tag audit."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from pyworkflowkit.cli_contract import CLI_COMMANDS, CLI_MACHINE_CONTRACT_VERSION
from pyworkflowkit.states import WorkflowRunStatus

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT / "contracts" / "release_evidence_v2_1.json"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _evidence() -> dict[str, object]:
    return json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))


def test_release_evidence_matches_package_and_cli_contract() -> None:
    evidence = _evidence()
    pyproject = tomllib.loads(_read("pyproject.toml"))

    assert evidence["target_version"] == pyproject["project"]["version"]
    assert evidence["qualified_version"] == "2.1.0"
    assert evidence["target_tag"] == "v2.1.1"
    assert (ROOT / "docs" / "releases" / "2.1.1.md").is_file()
    assert "## 2.1.1 - 2026-10-04" in _read("CHANGELOG.md")
    cli = evidence["cli_machine_contract"]
    assert isinstance(cli, dict)
    assert cli["version"] == CLI_MACHINE_CONTRACT_VERSION
    assert tuple(cli["commands"]) == CLI_COMMANDS

    baseline = evidence["remediation_baseline"]
    assert isinstance(baseline, dict)
    pytest_baseline = baseline["pytest"]
    assert isinstance(pytest_baseline, dict)
    assert pytest_baseline == {"passed": 1748, "skipped": 28, "failed": 0}


def test_release_docs_preserve_observed_v210_baseline_without_stale_aggregates() -> None:
    release_note = _read("docs/releases/2.1.0.md")
    roadmap = _read("ROADMAP.md")

    assert "1742 passed / 28 skipped / 0 failed" in release_note
    assert "1748 passed / 28 skipped / 0 failed" in roadmap
    assert "57/57" not in release_note
    assert "57/57" not in roadmap
    assert "1744 tests" not in release_note
    assert "1744 tests" not in roadmap


def test_current_docs_do_not_reintroduce_obsolete_release_claims() -> None:
    readme = _read("README.md")
    security = _read("SECURITY.md")
    agents = _read("AGENTS.md")
    claude = _read("CLAUDE.md")

    assert "PyWorkflowKit 2.1.1 is the current stable release line" in readme
    assert "PyWorkflowKit 2.0.0 is stable" not in readme
    assert "0.5.x is the current stable release line" not in security
    assert "57/57" not in agents
    assert "57/57" not in claude
    assert "Current release target: 2.1.1" in agents
    assert "Current release target: 2.1.1" in claude
    assert "3.14" not in agents
    assert "3.14" not in claude


def test_readme_primary_quickstart_is_executable() -> None:
    readme = _read("README.md")
    section = readme.split("### 1. Functional DAG Authoring with the `>>` Operator", maxsplit=1)[1]
    code = section.split("```python", maxsplit=1)[1].split("```", maxsplit=1)[0]

    namespace: dict[str, object] = {"__name__": "__readme_quickstart__"}
    exec(compile(code, "README.md::quickstart", "exec"), namespace)

    result = namespace["result"]
    assert result.status is WorkflowRunStatus.SUCCEEDED


def test_release_workflows_do_not_use_mutable_major_action_refs_or_latest_uv() -> None:
    publish = _read(".github/workflows/publish-pypi.yml")
    qualification = _read(".github/workflows/release-qualification.yml")
    workflows = publish + qualification

    assert "uses: actions/checkout@v" not in workflows
    assert "uses: actions/setup-python@v" not in workflows
    assert "uses: actions/upload-artifact@v" not in workflows
    assert "uses: actions/download-artifact@v" not in workflows
    assert "uses: actions/attest-build-provenance@v" not in workflows
    assert "uses: astral-sh/setup-uv@v" not in workflows
    assert "uses: softprops/action-gh-release@v" not in workflows
    assert "uses: pypa/gh-action-pypi-publish@release/" not in workflows
    assert 'version: "latest"' not in publish


def test_publish_workflow_requires_exact_sha_release_qualification() -> None:
    publish = _read(".github/workflows/publish-pypi.yml")

    assert "actions: read" in publish
    assert "release-qualification.yml/runs" in publish
    assert 'RELEASE_SHA="$(git rev-parse HEAD)"' in publish
    assert 'head_sha="$RELEASE_SHA"' in publish
    assert 'status="success"' in publish


def test_publish_workflow_isolates_pypi_distributions_from_release_assets() -> None:
    publish = _read(".github/workflows/publish-pypi.yml")

    assert "packages-dir: pypi-dist/" in publish
    assert "packages-dir: dist/" not in publish
    assert "mkdir -p pypi-dist release-assets" in publish
    assert "release-assets/pyworkflowkit-cyclonedx.json" in publish
    assert "tag_name: ${{ steps.release.outputs.tag }}" in publish


def test_publish_workflow_supports_immutable_tag_recovery_dispatch() -> None:
    publish = _read(".github/workflows/publish-pypi.yml")

    assert "release_tag:" in publish
    assert "Checkout release tag" in publish
    assert "ref: ${{ steps.release.outputs.tag }}" in publish
    assert 'RELEASE_SHA="$(git rev-parse HEAD)"' in publish
    assert 'head_sha="$RELEASE_SHA"' in publish
