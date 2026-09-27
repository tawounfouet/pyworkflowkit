"""RQ-05 acceptance for packaging and distribution contracts."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from pyworkflowkit.compatibility import COMPATIBILITY_SUBJECTS, CompatibilityStatus
from pyworkflowkit.contracts.distribution import (
    BUILD_BACKEND_REQUIREMENT,
    CONSOLE_SCRIPTS,
    DISTRIBUTION_ARTIFACTS,
    DISTRIBUTION_CONTRACT_VERSION,
    DISTRIBUTION_TARGET_RELEASE,
    FORBIDDEN_SDIST_PREFIXES,
    FORBIDDEN_WHEEL_PREFIXES,
    OPTIONAL_EXTRA_NAMES,
    PACKAGE_NAME,
    PYTHON_REQUIRES,
    REQUIRED_PROJECT_URL_NAMES,
    REQUIRED_SDIST_PATHS,
    REQUIRED_WHEEL_PATHS,
    RUNTIME_DEPENDENCY_RANGES,
    STABLE_UPGRADE_BASELINE_COMMIT,
    STABLE_UPGRADE_BASELINE_VERSION,
    distribution_contract_snapshot,
)
from pyworkflowkit.release_contract import REQUIRED_CONTRACT_VERSIONS, release_contract_snapshot

ROOT = Path(__file__).resolve().parents[2]


def _pyproject() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_rq05_distribution_contract_targets_1_0() -> None:
    assert DISTRIBUTION_CONTRACT_VERSION == "1"
    assert DISTRIBUTION_TARGET_RELEASE == "1.0.0"
    assert PACKAGE_NAME == "pyworkflowkit"
    assert PYTHON_REQUIRES == ">=3.11"
    assert DISTRIBUTION_ARTIFACTS == ("wheel", "sdist")
    assert STABLE_UPGRADE_BASELINE_VERSION == "0.8.0"
    assert STABLE_UPGRADE_BASELINE_COMMIT == "70cf048ca7264c9c6caf79fd28801f0db50973c5"


def test_rq05_pyproject_metadata_matches_distribution_contract() -> None:
    data = _pyproject()
    build_system = data["build-system"]
    project = data["project"]

    assert isinstance(build_system, dict)
    assert isinstance(project, dict)

    assert build_system["requires"] == [BUILD_BACKEND_REQUIREMENT]
    assert project["name"] == PACKAGE_NAME
    assert project["requires-python"] == PYTHON_REQUIRES
    assert project["dependencies"] == list(RUNTIME_DEPENDENCY_RANGES)
    assert tuple(sorted(project["optional-dependencies"])) == OPTIONAL_EXTRA_NAMES
    assert project["scripts"] == dict(CONSOLE_SCRIPTS)
    assert set(REQUIRED_PROJECT_URL_NAMES) <= set(project["urls"])


def test_rq05_sdist_scope_is_explicit() -> None:
    data = _pyproject()
    tool = data["tool"]

    assert isinstance(tool, dict)
    sdist = tool["hatch"]["build"]["targets"]["sdist"]
    assert sdist["include"] == [
        "/src/pyworkflowkit",
        "/README.md",
        "/CHANGELOG.md",
        "/SECURITY.md",
        "/pyproject.toml",
    ]


def test_rq05_artifact_path_contract_is_narrow() -> None:
    assert "pyworkflowkit/py.typed" in REQUIRED_WHEEL_PATHS
    assert "src/pyworkflowkit/py.typed" in REQUIRED_SDIST_PATHS

    for prefix in (
        ".github/",
        "docs/",
        "examples/",
        "qualification-integrations/",
        "reference-integrations/",
        "tests/",
        "typing-fixtures/",
    ):
        assert prefix in FORBIDDEN_WHEEL_PREFIXES
        assert prefix in FORBIDDEN_SDIST_PREFIXES


def test_rq05_readme_has_distribution_safe_guide_links() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "](docs/" not in readme
    assert "](examples/" not in readme
    assert "https://github.com/tawounfouet/pyworkflowkit/blob/main/docs/guides/" in readme


def test_rq05_is_stable_compatibility_evidence() -> None:
    matching = [
        subject
        for subject in COMPATIBILITY_SUBJECTS
        if subject.key == "distribution.artifact_contract"
    ]

    assert len(matching) == 1
    assert matching[0].status is CompatibilityStatus.STABLE
    assert matching[0].contract_version == "1"


def test_rq05_snapshot_is_json_portable_and_part_of_release_contract() -> None:
    snapshot = distribution_contract_snapshot()
    encoded = json.dumps(snapshot, allow_nan=False, sort_keys=True)

    assert json.loads(encoded) == snapshot
    assert dict(REQUIRED_CONTRACT_VERSIONS)["distribution"] == "1"

    release_snapshot = release_contract_snapshot()
    assert release_snapshot["contracts"]["distribution"] == "1"
    assert release_snapshot["distribution"] == snapshot
