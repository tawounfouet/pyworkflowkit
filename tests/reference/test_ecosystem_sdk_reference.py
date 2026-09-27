"""M52 reference acceptance for the ecosystem SDK public surface."""

from __future__ import annotations

import json

from pyworkflowkit.ecosystem import (
    ECOSYSTEM_COMPATIBILITY_SERIES,
    ECOSYSTEM_MAXIMUM_EXCLUSIVE_VERSION,
    ECOSYSTEM_MINIMUM_VERSION,
    ECOSYSTEM_SDK_CONTRACT_VERSION,
    ENTRY_POINT_GROUPS,
    PLUGIN_API_VERSION,
    ControlPlaneProvider,
    Executor,
    ExternalRunRef,
    ExternalWorkload,
    MetadataStore,
    PluginDescriptor,
    PluginDiscovery,
    PluginType,
    RuntimeEventSink,
    TaskResult,
    WorkflowRuntimeProvider,
    ecosystem_contract_snapshot,
)


def test_m52_ecosystem_sdk_surface_and_matrix_are_machine_readable() -> None:
    assert ECOSYSTEM_SDK_CONTRACT_VERSION == "1"
    assert ECOSYSTEM_COMPATIBILITY_SERIES == "0.8-0.9"
    assert ECOSYSTEM_MINIMUM_VERSION == "0.8.0b1"
    assert ECOSYSTEM_MAXIMUM_EXCLUSIVE_VERSION == "1.0"
    assert PLUGIN_API_VERSION == "1"
    assert ENTRY_POINT_GROUPS[PluginType.WORKLOAD] == "pyworkflowkit.workloads"

    public_contracts = (
        PluginDescriptor,
        PluginDiscovery,
        Executor,
        MetadataStore,
        RuntimeEventSink,
        ExternalWorkload,
        ExternalRunRef,
        TaskResult,
        ControlPlaneProvider,
        WorkflowRuntimeProvider,
    )
    assert all(value is not None for value in public_contracts)

    snapshot = ecosystem_contract_snapshot()
    encoded = json.dumps(snapshot, allow_nan=False, sort_keys=True)
    decoded = json.loads(encoded)

    assert decoded["sdk_contract_version"] == "1"
    assert decoded["supported_python_versions"] == ["3.11", "3.12", "3.13"]
    assert decoded["contracts"]["plugin_api"] == "1"
    assert decoded["contracts"]["control_plane"] == "1"
