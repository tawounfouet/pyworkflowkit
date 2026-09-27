"""Machine-readable ecosystem SDK compatibility contract."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from pyworkflowkit.control_plane import CONTROL_PLANE_PROVIDER_CONTRACT_VERSION
from pyworkflowkit.integrations import (
    EXTERNAL_WORKLOAD_CONTRACT_VERSION,
    OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION,
    REFERENCE_INTEROPERABILITY_CONTRACT_VERSION,
)
from pyworkflowkit.plugins import ENTRY_POINT_GROUPS, PLUGIN_API_VERSION, PluginType
from pyworkflowkit.release_contract import SUPPORTED_PYTHON_VERSIONS

ECOSYSTEM_SDK_CONTRACT_VERSION = "1"
ECOSYSTEM_COMPATIBILITY_SERIES = "0.8"
ECOSYSTEM_MINIMUM_VERSION = "0.8.0b1"
ECOSYSTEM_MAXIMUM_EXCLUSIVE_VERSION = "0.9"


def ecosystem_contract_snapshot() -> dict[str, object]:
    """Return deterministic machine-readable metadata for integration authors."""

    try:
        package_version = version("pyworkflowkit")
    except PackageNotFoundError:  # pragma: no cover - source-tree fallback
        package_version = "0.0.0+unknown"

    return {
        "package_version": package_version,
        "sdk_contract_version": ECOSYSTEM_SDK_CONTRACT_VERSION,
        "compatibility": {
            "series": ECOSYSTEM_COMPATIBILITY_SERIES,
            "minimum": ECOSYSTEM_MINIMUM_VERSION,
            "maximum_exclusive": ECOSYSTEM_MAXIMUM_EXCLUSIVE_VERSION,
        },
        "supported_python_versions": list(SUPPORTED_PYTHON_VERSIONS),
        "contracts": {
            "control_plane": CONTROL_PLANE_PROVIDER_CONTRACT_VERSION,
            "external_workload": EXTERNAL_WORKLOAD_CONTRACT_VERSION,
            "observability": OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION,
            "plugin_api": PLUGIN_API_VERSION,
            "references": REFERENCE_INTEROPERABILITY_CONTRACT_VERSION,
        },
        "entry_point_groups": {
            plugin_type.value: ENTRY_POINT_GROUPS[plugin_type] for plugin_type in PluginType
        },
    }


__all__ = [
    "ECOSYSTEM_COMPATIBILITY_SERIES",
    "ECOSYSTEM_MAXIMUM_EXCLUSIVE_VERSION",
    "ECOSYSTEM_MINIMUM_VERSION",
    "ECOSYSTEM_SDK_CONTRACT_VERSION",
    "ecosystem_contract_snapshot",
]
