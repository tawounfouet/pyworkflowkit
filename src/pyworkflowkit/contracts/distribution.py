"""Machine-readable packaging and distribution contract for the PyWorkflowKit 1.0 line."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

DISTRIBUTION_CONTRACT_VERSION = "1"
DISTRIBUTION_TARGET_RELEASE = "1.0.0"
BUILD_BACKEND_REQUIREMENT = "hatchling>=1.27,<2"
PACKAGE_NAME = "pyworkflowkit"
PYTHON_REQUIRES = ">=3.11"
STABLE_UPGRADE_BASELINE_VERSION = "0.8.0"
STABLE_UPGRADE_BASELINE_COMMIT = "70cf048ca7264c9c6caf79fd28801f0db50973c5"

DISTRIBUTION_ARTIFACTS: tuple[str, ...] = ("wheel", "sdist")
CONSOLE_SCRIPTS: Mapping[str, str] = MappingProxyType(
    {
        "pyworkflow": "pyworkflowkit.cli:main",
        "pyworkflowkit": "pyworkflowkit.cli:main",
    }
)

RUNTIME_DEPENDENCY_RANGES: tuple[str, ...] = (
    "alembic>=1.16,<2",
    "pydantic>=2.13,<3",
    "pydantic-settings>=2.11,<3",
    "sqlalchemy>=2.0,<3",
    "typer>=0.12,<1",
)

OPTIONAL_EXTRA_NAMES: tuple[str, ...] = (
    "dev",
    "postgres",
    "security",
)

REQUIRED_PROJECT_URL_NAMES: tuple[str, ...] = (
    "Changelog",
    "Documentation",
    "Homepage",
    "Issues",
    "Repository",
    "Security",
)

REQUIRED_WHEEL_PATHS: tuple[str, ...] = (
    "pyworkflowkit/__init__.py",
    "pyworkflowkit/py.typed",
    "pyworkflowkit/migrations/versions/0001_runtime_metadata.py",
    "pyworkflowkit/migrations/versions/0002_task_output_checkpoints.py",
    "pyworkflowkit/migrations/versions/0003_retry_eligible_at.py",
)

FORBIDDEN_WHEEL_PREFIXES: tuple[str, ...] = (
    ".github/",
    "docs/",
    "ecosystem-template/",
    "examples/",
    "qualification-integrations/",
    "reference-integrations/",
    "tests/",
    "typing-fixtures/",
)

REQUIRED_SDIST_PATHS: tuple[str, ...] = (
    "CHANGELOG.md",
    "README.md",
    "SECURITY.md",
    "pyproject.toml",
    "src/pyworkflowkit/__init__.py",
    "src/pyworkflowkit/py.typed",
    "src/pyworkflowkit/migrations/versions/0001_runtime_metadata.py",
    "src/pyworkflowkit/migrations/versions/0002_task_output_checkpoints.py",
    "src/pyworkflowkit/migrations/versions/0003_retry_eligible_at.py",
)

FORBIDDEN_SDIST_PREFIXES: tuple[str, ...] = (
    ".github/",
    "docs/",
    "ecosystem-template/",
    "examples/",
    "qualification-integrations/",
    "reference-integrations/",
    "tests/",
    "typing-fixtures/",
)


def distribution_contract_snapshot() -> dict[str, object]:
    """Return deterministic RQ-05 packaging/distribution metadata."""

    return {
        "contract_version": DISTRIBUTION_CONTRACT_VERSION,
        "target_release": DISTRIBUTION_TARGET_RELEASE,
        "package_name": PACKAGE_NAME,
        "python_requires": PYTHON_REQUIRES,
        "build_backend_requirement": BUILD_BACKEND_REQUIREMENT,
        "artifacts": list(DISTRIBUTION_ARTIFACTS),
        "console_scripts": dict(sorted(CONSOLE_SCRIPTS.items())),
        "runtime_dependencies": list(RUNTIME_DEPENDENCY_RANGES),
        "optional_extras": list(OPTIONAL_EXTRA_NAMES),
        "required_project_urls": list(REQUIRED_PROJECT_URL_NAMES),
        "upgrade_baseline": {
            "version": STABLE_UPGRADE_BASELINE_VERSION,
            "commit": STABLE_UPGRADE_BASELINE_COMMIT,
        },
        "wheel": {
            "required_paths": list(REQUIRED_WHEEL_PATHS),
            "forbidden_prefixes": list(FORBIDDEN_WHEEL_PREFIXES),
        },
        "sdist": {
            "required_paths": list(REQUIRED_SDIST_PATHS),
            "forbidden_prefixes": list(FORBIDDEN_SDIST_PREFIXES),
        },
    }


__all__ = [
    "BUILD_BACKEND_REQUIREMENT",
    "CONSOLE_SCRIPTS",
    "DISTRIBUTION_ARTIFACTS",
    "DISTRIBUTION_CONTRACT_VERSION",
    "DISTRIBUTION_TARGET_RELEASE",
    "FORBIDDEN_SDIST_PREFIXES",
    "FORBIDDEN_WHEEL_PREFIXES",
    "OPTIONAL_EXTRA_NAMES",
    "PACKAGE_NAME",
    "PYTHON_REQUIRES",
    "REQUIRED_PROJECT_URL_NAMES",
    "REQUIRED_SDIST_PATHS",
    "REQUIRED_WHEEL_PATHS",
    "RUNTIME_DEPENDENCY_RANGES",
    "STABLE_UPGRADE_BASELINE_COMMIT",
    "STABLE_UPGRADE_BASELINE_VERSION",
    "distribution_contract_snapshot",
]
