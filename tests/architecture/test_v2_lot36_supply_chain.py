"""Tests verifying LOT-36 Release Automation, PyPI OIDC, SBOM and Supply Chain compliance."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_license_file_exists_and_contains_apache_2_0() -> None:
    license_file = REPO_ROOT / "LICENSE"
    assert license_file.is_file(), "Canonical LICENSE file must exist at repo root"
    content = license_file.read_text(encoding="utf-8")
    assert "Apache License" in content
    assert "Version 2.0, January 2004" in content
    assert "Copyright 2026 Thomas AWOUNFOUET / Webtech Engineering" in content


def test_pyproject_toml_has_explicit_spdx_license_and_classifier() -> None:
    pyproject_file = REPO_ROOT / "pyproject.toml"
    assert pyproject_file.is_file()
    data = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
    project = data["project"]

    # PEP 621 / PEP 639 license
    assert "license" in project
    assert project["license"] == {"text": "Apache-2.0"}

    # Classifiers
    classifiers = project.get("classifiers", [])
    assert "License :: OSI Approved :: Apache Software License" in classifiers


def test_publish_pypi_workflow_specification() -> None:
    workflow_path = REPO_ROOT / ".github" / "workflows" / "publish-pypi.yml"
    assert workflow_path.is_file(), "publish-pypi.yml workflow must exist"
    content = workflow_path.read_text(encoding="utf-8")

    # Trusted Publishing OIDC & Attestations permissions
    assert "id-token: write" in content
    assert "attestations: write" in content
    assert "contents: write" in content

    # Environment
    assert "name: pypi" in content
    assert "https://pypi.org/p/pyworkflowkit" in content

    # Supply Chain components
    assert "cyclonedx-py environment" in content
    assert "pyworkflowkit-cyclonedx.json" in content
    assert "SHA256SUMS" in content
    assert "actions/attest-build-provenance" in content
    assert "pypa/gh-action-pypi-publish" in content


def test_release_playbook_guide_exists() -> None:
    guide_path = REPO_ROOT / "docs" / "guides" / "release-playbook.md"
    assert guide_path.is_file(), "docs/guides/release-playbook.md must exist"
    content = guide_path.read_text(encoding="utf-8")
    assert "Release Playbook" in content
    assert "CycloneDX SBOM" in content
    assert "Trusted Publishing" in content
    assert "Sigstore" in content
