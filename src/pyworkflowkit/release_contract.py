"""Release qualification contract assembled from compatibility milestones."""

from __future__ import annotations

from collections.abc import Mapping
from importlib.metadata import version
from types import MappingProxyType

from pyworkflowkit.application.manifest import MANIFEST_SCHEMA_VERSION
from pyworkflowkit.cli_contract import CLI_MACHINE_CONTRACT_VERSION
from pyworkflowkit.compatibility import compatibility_contract_snapshot
from pyworkflowkit.contracts.developer_experience import (
    DX_CONTRACT_VERSION,
    developer_experience_contract_snapshot,
)
from pyworkflowkit.contracts.distribution import (
    DISTRIBUTION_CONTRACT_VERSION,
    distribution_contract_snapshot,
)
from pyworkflowkit.contracts.release_candidate import (
    RELEASE_CANDIDATE_CONTRACT_VERSION,
    release_candidate_contract_snapshot,
)
from pyworkflowkit.contracts.typing import TYPING_CONTRACT_VERSION, typing_contract_snapshot
from pyworkflowkit.migrations.contract import (
    MIGRATION_HEAD_REVISION,
    PERSISTENCE_SCHEMA_CONTRACT_VERSION,
)
from pyworkflowkit.plugins.model import PLUGIN_API_VERSION

RELEASE_QUALIFICATION_CONTRACT_VERSION = "1"

SUPPORTED_PYTHON_VERSIONS: tuple[str, ...] = (
    "3.11",
    "3.12",
    "3.13",
)

REQUIRED_CONTRACT_VERSIONS: Mapping[str, str] = MappingProxyType(
    {
        "cli_machine": CLI_MACHINE_CONTRACT_VERSION,
        "developer_experience": DX_CONTRACT_VERSION,
        "distribution": DISTRIBUTION_CONTRACT_VERSION,
        "manifest": MANIFEST_SCHEMA_VERSION,
        "persistence": PERSISTENCE_SCHEMA_CONTRACT_VERSION,
        "plugin_api": PLUGIN_API_VERSION,
        "release_candidate": RELEASE_CANDIDATE_CONTRACT_VERSION,
        "typing": TYPING_CONTRACT_VERSION,
    }
)


def release_contract_snapshot() -> dict[str, object]:
    """Return deterministic release-facing compatibility metadata."""

    return {
        "package_version": version("pyworkflowkit"),
        "qualification_contract_version": RELEASE_QUALIFICATION_CONTRACT_VERSION,
        "supported_python_versions": list(SUPPORTED_PYTHON_VERSIONS),
        "contracts": dict(sorted(REQUIRED_CONTRACT_VERSIONS.items())),
        "migration_head": MIGRATION_HEAD_REVISION,
        "compatibility": compatibility_contract_snapshot(),
        "developer_experience": developer_experience_contract_snapshot(),
        "distribution": distribution_contract_snapshot(),
        "release_candidate": release_candidate_contract_snapshot(),
        "typing": typing_contract_snapshot(),
    }


__all__ = [
    "RELEASE_QUALIFICATION_CONTRACT_VERSION",
    "REQUIRED_CONTRACT_VERSIONS",
    "SUPPORTED_PYTHON_VERSIONS",
    "release_contract_snapshot",
]
