"""LOT-16 unit tests for the canonical V2 plugin migration contract."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from pyworkflowkit.adapters.executors.local import LocalExecutor as LegacyLocalExecutor
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.plugins import (
    PLUGIN_API_VERSION,
    PluginDescriptor,
    PluginType,
    RegisteredPlugin,
)
from pyworkflowkit.plugins.v2 import (
    V2_ENTRY_POINT_GROUPS,
    V2_PLUGIN_API_VERSION,
    V2PluginCatalog,
    V2PluginDescriptor,
    V2RegisteredPlugin,
    V2RuntimeEventSink,
    V2WorkloadBinding,
    assert_v2_plugin_instance_compatible,
    v2_plugin_contract_snapshot,
    validate_v2_plugin_instance,
    validate_v2_plugin_registration,
)
from pyworkflowkit.runtime import RuntimeEvent


@dataclass
class RecordingSink:
    events: list[RuntimeEvent] = field(default_factory=list)

    @property
    def name(self) -> str:
        return "recording-v2"

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)


def _registration(
    name: str,
    plugin_type: PluginType,
    factory: object,
) -> V2RegisteredPlugin[object]:
    assert callable(factory)
    return V2RegisteredPlugin(
        descriptor=V2PluginDescriptor(
            name=name,
            plugin_type=plugin_type,
            api_version=V2_PLUGIN_API_VERSION,
        ),
        factory=factory,
    )


def test_lot16_v2_entry_point_groups_are_disjoint_from_v1() -> None:
    assert V2_PLUGIN_API_VERSION == "2"
    assert PLUGIN_API_VERSION == "1"
    assert set(V2_ENTRY_POINT_GROUPS.values()) == {
        "pyworkflowkit.v2.executors",
        "pyworkflowkit.v2.metadata",
        "pyworkflowkit.v2.workloads",
        "pyworkflowkit.v2.events",
    }


def test_lot16_legacy_registration_is_not_implicitly_v2_compatible() -> None:
    legacy = RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="legacy",
            plugin_type=PluginType.EXECUTOR,
            api_version=PLUGIN_API_VERSION,
        ),
        factory=LegacyLocalExecutor,
    )

    report = validate_v2_plugin_registration(
        legacy,
        entry_point_name="legacy",
        entry_point_group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
    )

    assert report.compatible is False
    assert report.descriptor is None
    assert any(issue.code.value == "registration_type" for issue in report.issues)


def test_lot16_executor_contract_targets_canonical_v2_executor() -> None:
    assert validate_v2_plugin_instance(
        InlineExecutor(),
        plugin_type=PluginType.EXECUTOR,
    ).compatible

    legacy_report = validate_v2_plugin_instance(
        LegacyLocalExecutor(),
        plugin_type=PluginType.EXECUTOR,
    )
    assert legacy_report.compatible is False


def test_lot16_catalog_validates_all_four_plugin_categories_on_creation() -> None:
    catalog = V2PluginCatalog()

    catalog.executors.register(
        _registration("inline-v2", PluginType.EXECUTOR, InlineExecutor)
    )
    catalog.metadata.register(
        _registration("memory-v2", PluginType.METADATA, InMemoryMetadataStore)
    )
    catalog.workloads.register(
        _registration(
            "hello-v2",
            PluginType.WORKLOAD,
            lambda: V2WorkloadBinding(
                registry_key="hello.v2",
                handler=lambda: "hello",
            ),
        )
    )
    catalog.events.register(
        _registration("events-v2", PluginType.EVENT, RecordingSink)
    )

    assert isinstance(catalog.executors.create("inline-v2"), InlineExecutor)
    assert isinstance(catalog.metadata.create("memory-v2"), InMemoryMetadataStore)
    workload = catalog.workloads.create("hello-v2")
    assert workload.registry_key == "hello.v2"
    assert workload.handler() == "hello"
    assert isinstance(catalog.events.create("events-v2"), V2RuntimeEventSink)


def test_lot16_catalog_fails_closed_on_wrong_instance_contract() -> None:
    catalog = V2PluginCatalog()
    catalog.executors.register(
        _registration("wrong", PluginType.EXECUTOR, lambda: object())
    )

    with pytest.raises(Exception, match="does not satisfy"):
        catalog.executors.create("wrong")


def test_lot16_registration_rejects_wrong_api_version() -> None:
    registration = V2RegisteredPlugin(
        descriptor=V2PluginDescriptor(
            name="wrong-version",
            plugin_type=PluginType.EXECUTOR,
            api_version="1",
        ),
        factory=InlineExecutor,
    )

    report = validate_v2_plugin_registration(
        registration,
        entry_point_name="wrong-version",
        entry_point_group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
    )

    assert report.compatible is False
    assert any(issue.code.value == "api_version" for issue in report.issues)


def test_lot16_snapshot_freezes_migration_posture() -> None:
    snapshot = v2_plugin_contract_snapshot()

    assert snapshot["contract_version"] == "1"
    assert snapshot["plugin_api_version"] == "2"
    assert snapshot["metadata_first_discovery"] is True
    assert snapshot["explicit_enablement"] is True
    assert snapshot["implicit_v1_bridge"] is False
    assert snapshot["instantiate_during_registration_validation"] is False


def test_lot16_explicit_instance_assertion_accepts_workload_binding() -> None:
    binding = V2WorkloadBinding(registry_key="jobs.refresh", handler=lambda: None)
    report = assert_v2_plugin_instance_compatible(
        binding,
        plugin_type=PluginType.WORKLOAD,
    )
    assert report.compatible
