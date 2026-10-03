"""LOT-16 reference acceptance for additive V2 plugin migration."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.plugins as legacy_plugins
import pyworkflowkit.plugins.v2 as plugins_v2

from pyworkflowkit.plugins import PluginType


def test_lot16_v2_plugin_surface_is_qualified_not_root_promoted() -> None:
    required = {
        "V2PluginCatalog",
        "V2PluginDescriptor",
        "V2PluginDiscovery",
        "V2PluginRegistry",
        "V2RegisteredPlugin",
        "V2RuntimeEventSink",
        "V2WorkloadBinding",
        "V2_ENTRY_POINT_GROUPS",
        "V2_PLUGIN_API_VERSION",
        "v2_plugin_contract_snapshot",
    }
    assert required.issubset(set(plugins_v2.__all__))

    for name in required:
        assert name not in pyworkflowkit.__all__
        assert name not in legacy_plugins.__all__


def test_lot16_frozen_v1_plugin_contract_remains_unchanged() -> None:
    assert legacy_plugins.PLUGIN_API_VERSION == "1"
    assert legacy_plugins.ENTRY_POINT_GROUPS == {
        PluginType.EXECUTOR: "pyworkflowkit.executors",
        PluginType.METADATA: "pyworkflowkit.metadata",
        PluginType.WORKLOAD: "pyworkflowkit.workloads",
        PluginType.EVENT: "pyworkflowkit.events",
    }


def test_lot16_v2_contract_uses_separate_entry_point_namespace() -> None:
    assert plugins_v2.V2_PLUGIN_API_VERSION == "2"
    assert plugins_v2.V2_ENTRY_POINT_GROUPS == {
        PluginType.EXECUTOR: "pyworkflowkit.v2.executors",
        PluginType.METADATA: "pyworkflowkit.v2.metadata",
        PluginType.WORKLOAD: "pyworkflowkit.v2.workloads",
        PluginType.EVENT: "pyworkflowkit.v2.events",
    }

    assert set(plugins_v2.V2_ENTRY_POINT_GROUPS.values()).isdisjoint(
        set(legacy_plugins.ENTRY_POINT_GROUPS.values())
    )


def test_lot16_snapshot_targets_canonical_v2_runtime_contracts() -> None:
    snapshot = plugins_v2.v2_plugin_contract_snapshot()

    assert snapshot == {
        "contract_version": "1",
        "plugin_api_version": "2",
        "entry_point_groups": {
            "executor": "pyworkflowkit.v2.executors",
            "metadata": "pyworkflowkit.v2.metadata",
            "workload": "pyworkflowkit.v2.workloads",
            "event": "pyworkflowkit.v2.events",
        },
        "plugin_types": ["executor", "metadata", "workload", "event"],
        "executor_contract": "pyworkflowkit.executors.Executor",
        "metadata_contract": "pyworkflowkit.persistence.MetadataStore",
        "workload_contract": "V2WorkloadBinding",
        "event_contract": "V2RuntimeEventSink[pyworkflowkit.runtime.RuntimeEvent]",
        "metadata_first_discovery": True,
        "explicit_enablement": True,
        "implicit_v1_bridge": False,
        "instantiate_during_registration_validation": False,
    }
