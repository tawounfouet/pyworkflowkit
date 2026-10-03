"""LOT-16 unit tests for the canonical V2 plugin migration contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from pyworkflowkit.adapters.executors.local import LocalExecutor as LegacyLocalExecutor
from pyworkflowkit.errors import (
    DuplicatePluginError,
    PluginCompatibilityError,
    PluginLoadError,
    PluginNotFoundError,
    PluginTypeMismatchError,
)
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
    V2DiscoveredPlugin,
    V2PluginCatalog,
    V2PluginContractIssue,
    V2PluginContractIssueCode,
    V2PluginContractReport,
    V2PluginDescriptor,
    V2PluginDiscovery,
    V2PluginDiscoveryResult,
    V2PluginDiscoveryStatus,
    V2PluginInstanceContractReport,
    V2PluginRegistry,
    V2RegisteredPlugin,
    V2RuntimeEventSink,
    V2WorkloadBinding,
    assert_v2_plugin_instance_compatible,
    assert_v2_plugin_registration_compatible,
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


class _FakeEntryPoint:
    def __init__(
        self,
        *,
        name: str,
        group: str,
        value: str,
        loaded: object = None,
        error: Exception | None = None,
        distribution: str = "lot16-fixture",
    ) -> None:
        self.name = name
        self.group = group
        self.value = value
        self.dist = SimpleNamespace(name=distribution)
        self._loaded = loaded
        self._error = error
        self.load_count = 0

    def load(self) -> object:
        self.load_count += 1
        if self._error is not None:
            raise self._error
        return self._loaded


class _FakeEntryPoints(tuple[_FakeEntryPoint, ...]):
    def select(self, *, group: str) -> tuple[_FakeEntryPoint, ...]:
        return tuple(item for item in self if item.group == group)


def _registration(
    name: str,
    plugin_type: PluginType,
    factory: object,
) -> V2RegisteredPlugin[object]:
    if not callable(factory):
        raise TypeError("fixture factory must be callable")
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


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"name": "", "plugin_type": PluginType.EXECUTOR}, ValueError),
        ({"name": 42, "plugin_type": PluginType.EXECUTOR}, TypeError),
        ({"name": "x", "plugin_type": "executor"}, TypeError),
        (
            {
                "name": "x",
                "plugin_type": PluginType.EXECUTOR,
                "api_version": "",
            },
            ValueError,
        ),
        (
            {
                "name": "x",
                "plugin_type": PluginType.EXECUTOR,
                "plugin_version": "",
            },
            ValueError,
        ),
        (
            {
                "name": "x",
                "plugin_type": PluginType.EXECUTOR,
                "description": "",
            },
            ValueError,
        ),
    ],
)
def test_lot16_descriptor_validation_fails_closed(
    kwargs: dict[str, object],
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        V2PluginDescriptor(**kwargs)  # type: ignore[arg-type]


def test_lot16_workload_binding_requires_key_and_callable() -> None:
    with pytest.raises(ValueError, match="registry_key"):
        V2WorkloadBinding(registry_key="", handler=lambda: None)
    with pytest.raises(TypeError, match="handler"):
        V2WorkloadBinding(registry_key="jobs.x", handler=object())  # type: ignore[arg-type]


def test_lot16_registered_plugin_validates_descriptor_and_factory() -> None:
    descriptor = V2PluginDescriptor(name="x", plugin_type=PluginType.EXECUTOR)
    with pytest.raises(TypeError, match="descriptor"):
        V2RegisteredPlugin(descriptor=object(), factory=InlineExecutor)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="factory"):
        V2RegisteredPlugin(descriptor=descriptor, factory=object())  # type: ignore[arg-type]


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
    assert report.plugin_type is PluginType.EXECUTOR
    assert any(issue.code is V2PluginContractIssueCode.REGISTRATION_TYPE for issue in report.issues)
    assert "V2RegisteredPlugin" in report.summary()


def test_lot16_registration_reports_unknown_group_name_type_and_version() -> None:
    registration = V2RegisteredPlugin(
        descriptor=V2PluginDescriptor(
            name="descriptor-name",
            plugin_type=PluginType.METADATA,
            api_version="1",
        ),
        factory=InMemoryMetadataStore,
    )

    unknown = validate_v2_plugin_registration(
        registration,
        entry_point_name="entry-name",
        entry_point_group="pyworkflowkit.v2.unknown",
    )
    assert unknown.compatible is False
    assert unknown.plugin_type is None
    assert {
        issue.code for issue in unknown.issues
    } >= {
        V2PluginContractIssueCode.ENTRY_POINT_GROUP,
        V2PluginContractIssueCode.DESCRIPTOR_NAME,
        V2PluginContractIssueCode.API_VERSION,
    }

    mismatch = validate_v2_plugin_registration(
        registration,
        entry_point_name="entry-name",
        entry_point_group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
    )
    assert {
        issue.code for issue in mismatch.issues
    } >= {
        V2PluginContractIssueCode.DESCRIPTOR_NAME,
        V2PluginContractIssueCode.DESCRIPTOR_TYPE,
        V2PluginContractIssueCode.API_VERSION,
    }

    with pytest.raises(PluginCompatibilityError):
        assert_v2_plugin_registration_compatible(
            registration,
            entry_point_name="entry-name",
            entry_point_group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        )


def test_lot16_compatible_registration_report_has_stable_summary() -> None:
    registration = _registration("inline", PluginType.EXECUTOR, InlineExecutor)
    report = assert_v2_plugin_registration_compatible(
        registration,
        entry_point_name="inline",
        entry_point_group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
    )
    assert report.compatible
    assert report.plugin_type is PluginType.EXECUTOR
    assert "plugin API 2" in report.summary()


def test_lot16_registration_validates_non_blank_entry_point_identity() -> None:
    registration = _registration("inline", PluginType.EXECUTOR, InlineExecutor)
    with pytest.raises(ValueError, match="entry_point_name"):
        validate_v2_plugin_registration(
            registration,
            entry_point_name="",
            entry_point_group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        )
    with pytest.raises(ValueError, match="entry_point_group"):
        validate_v2_plugin_registration(
            registration,
            entry_point_name="inline",
            entry_point_group="",
        )


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
    assert "pyworkflowkit.executors.Executor" in legacy_report.summary()


def test_lot16_instance_validation_covers_all_four_categories() -> None:
    metadata = InMemoryMetadataStore()
    workload = V2WorkloadBinding(registry_key="jobs.refresh", handler=lambda: None)
    event_sink = RecordingSink()

    assert validate_v2_plugin_instance(
        metadata,
        plugin_type=PluginType.METADATA,
    ).compatible
    assert validate_v2_plugin_instance(
        workload,
        plugin_type=PluginType.WORKLOAD,
    ).compatible
    assert validate_v2_plugin_instance(
        event_sink,
        plugin_type=PluginType.EVENT,
    ).compatible

    for plugin_type in (PluginType.METADATA, PluginType.WORKLOAD, PluginType.EVENT):
        report = validate_v2_plugin_instance(object(), plugin_type=plugin_type)
        assert report.compatible is False
        with pytest.raises(PluginCompatibilityError):
            assert_v2_plugin_instance_compatible(object(), plugin_type=plugin_type)

    with pytest.raises(TypeError, match="PluginType"):
        validate_v2_plugin_instance(object(), plugin_type="executor")  # type: ignore[arg-type]


def test_lot16_instance_report_summaries_cover_both_paths() -> None:
    compatible = V2PluginInstanceContractReport(
        plugin_type=PluginType.WORKLOAD,
        issues=(),
    )
    incompatible = V2PluginInstanceContractReport(
        plugin_type=PluginType.WORKLOAD,
        issues=(
            V2PluginContractIssue(
                code=V2PluginContractIssueCode.INSTANCE_TYPE,
                message="wrong workload",
            ),
        ),
    )
    assert "satisfies V2 plugin API" in compatible.summary()
    assert incompatible.summary() == "wrong workload"


def test_lot16_catalog_validates_all_four_plugin_categories_on_creation() -> None:
    catalog = V2PluginCatalog()

    catalog.executors.register(_registration("inline-v2", PluginType.EXECUTOR, InlineExecutor))
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
    catalog.events.register(_registration("events-v2", PluginType.EVENT, RecordingSink))

    assert isinstance(catalog.executors.create("inline-v2"), InlineExecutor)
    assert isinstance(catalog.metadata.create("memory-v2"), InMemoryMetadataStore)
    workload = catalog.workloads.create("hello-v2")
    assert workload.registry_key == "hello.v2"
    assert workload.handler() == "hello"
    assert isinstance(catalog.events.create("events-v2"), V2RuntimeEventSink)

    assert "inline-v2" in catalog.executors
    assert object() not in catalog.executors
    assert len(catalog.executors) == 1
    assert catalog.executors.descriptors()[0].name == "inline-v2"
    assert [item.plugin_type for item in catalog.descriptors()] == [
        PluginType.EVENT,
        PluginType.EXECUTOR,
        PluginType.METADATA,
        PluginType.WORKLOAD,
    ]


def test_lot16_registry_guards_are_fail_closed() -> None:
    with pytest.raises(TypeError, match="PluginType"):
        V2PluginRegistry(plugin_type="executor")  # type: ignore[arg-type]

    registry: V2PluginRegistry[object] = V2PluginRegistry(
        plugin_type=PluginType.EXECUTOR
    )
    with pytest.raises(TypeError, match="V2RegisteredPlugin"):
        registry.register(object())  # type: ignore[arg-type]

    wrong_type = _registration("metadata", PluginType.METADATA, InMemoryMetadataStore)
    with pytest.raises(PluginTypeMismatchError):
        registry.register(wrong_type)

    wrong_version = V2RegisteredPlugin(
        descriptor=V2PluginDescriptor(
            name="old",
            plugin_type=PluginType.EXECUTOR,
            api_version="1",
        ),
        factory=InlineExecutor,
    )
    with pytest.raises(PluginCompatibilityError):
        registry.register(wrong_version)

    valid = _registration("inline", PluginType.EXECUTOR, InlineExecutor)
    registry.register(valid)
    with pytest.raises(DuplicatePluginError):
        registry.register(valid)
    with pytest.raises(PluginNotFoundError):
        registry.get("missing")


def test_lot16_catalog_registry_for_covers_every_category() -> None:
    catalog = V2PluginCatalog()
    assert catalog.registry_for(PluginType.EXECUTOR).plugin_type is PluginType.EXECUTOR
    assert catalog.registry_for(PluginType.METADATA).plugin_type is PluginType.METADATA
    assert catalog.registry_for(PluginType.WORKLOAD).plugin_type is PluginType.WORKLOAD
    assert catalog.registry_for(PluginType.EVENT).plugin_type is PluginType.EVENT


def test_lot16_catalog_fails_closed_on_wrong_instance_contract() -> None:
    catalog = V2PluginCatalog()
    catalog.executors.register(_registration("wrong", PluginType.EXECUTOR, lambda: object()))

    with pytest.raises(PluginCompatibilityError, match="does not satisfy"):
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
    assert any(issue.code is V2PluginContractIssueCode.API_VERSION for issue in report.issues)


def test_lot16_discovery_is_metadata_first_and_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    executor_ep = _FakeEntryPoint(
        name="z-executor",
        group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        value="fixture:z",
        loaded=lambda: _registration("z-executor", PluginType.EXECUTOR, InlineExecutor),
    )
    workload_ep = _FakeEntryPoint(
        name="a-workload",
        group=V2_ENTRY_POINT_GROUPS[PluginType.WORKLOAD],
        value="fixture:a",
        loaded=lambda: _registration(
            "a-workload",
            PluginType.WORKLOAD,
            lambda: V2WorkloadBinding(registry_key="a", handler=lambda: None),
        ),
    )
    monkeypatch.setattr(
        "pyworkflowkit.plugins.v2.importlib_metadata.entry_points",
        lambda: _FakeEntryPoints((executor_ep, workload_ep)),
    )

    discovered = V2PluginDiscovery().discover()
    assert [(item.plugin_type, item.name) for item in discovered] == [
        (PluginType.EXECUTOR, "z-executor"),
        (PluginType.WORKLOAD, "a-workload"),
    ]
    assert executor_ep.load_count == 0
    assert workload_ep.load_count == 0
    assert discovered[0].distribution == "lot16-fixture"


def test_lot16_discovery_enablement_registers_only_explicit_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = _FakeEntryPoint(
        name="selected",
        group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        value="fixture:selected",
        loaded=lambda: _registration("selected", PluginType.EXECUTOR, InlineExecutor),
    )
    untouched = _FakeEntryPoint(
        name="untouched",
        group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        value="fixture:untouched",
        loaded=lambda: _registration("untouched", PluginType.EXECUTOR, InlineExecutor),
    )
    monkeypatch.setattr(
        "pyworkflowkit.plugins.v2.importlib_metadata.entry_points",
        lambda: _FakeEntryPoints((untouched, selected)),
    )

    catalog = V2PluginCatalog()
    report = V2PluginDiscovery().enable_selected(
        catalog=catalog,
        enabled={PluginType.EXECUTOR: {"selected"}},
    )

    assert [result.status for result in report.results] == [
        V2PluginDiscoveryStatus.REGISTERED,
        V2PluginDiscoveryStatus.DISCOVERED,
    ]
    assert report.has_errors is False
    assert selected.load_count == 1
    assert untouched.load_count == 0
    assert isinstance(catalog.executors.create("selected"), InlineExecutor)


def test_lot16_discovery_missing_explicit_plugin_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pyworkflowkit.plugins.v2.importlib_metadata.entry_points",
        lambda: _FakeEntryPoints(),
    )
    with pytest.raises(PluginNotFoundError):
        V2PluginDiscovery().enable_selected(
            catalog=V2PluginCatalog(),
            enabled={PluginType.EXECUTOR: {"missing"}},
        )


def test_lot16_discovery_marks_incompatible_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="legacy",
            plugin_type=PluginType.EXECUTOR,
        ),
        factory=LegacyLocalExecutor,
    )
    entry_point = _FakeEntryPoint(
        name="legacy",
        group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        value="fixture:legacy",
        loaded=lambda: legacy,
    )
    monkeypatch.setattr(
        "pyworkflowkit.plugins.v2.importlib_metadata.entry_points",
        lambda: _FakeEntryPoints((entry_point,)),
    )

    report = V2PluginDiscovery().enable_selected(
        catalog=V2PluginCatalog(),
        enabled={PluginType.EXECUTOR: {"legacy"}},
    )
    assert report.has_errors
    assert report.results[0].status is V2PluginDiscoveryStatus.INCOMPATIBLE
    assert report.results[0].descriptor is None
    assert "V2RegisteredPlugin" in (report.results[0].error or "")


@pytest.mark.parametrize(
    "error",
    [RuntimeError("boom"), PluginLoadError(plugin_name="broken", reason="fixture")],
)
def test_lot16_discovery_marks_load_failures(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    entry_point = _FakeEntryPoint(
        name="broken",
        group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        value="fixture:broken",
        error=error,
    )
    monkeypatch.setattr(
        "pyworkflowkit.plugins.v2.importlib_metadata.entry_points",
        lambda: _FakeEntryPoints((entry_point,)),
    )

    report = V2PluginDiscovery().enable_selected(
        catalog=V2PluginCatalog(),
        enabled={PluginType.EXECUTOR: {"broken"}},
    )
    assert report.has_errors
    assert report.results[0].status is V2PluginDiscoveryStatus.FAILED
    assert report.results[0].error


def test_lot16_discovery_value_objects_are_immutable_contracts() -> None:
    discovered = V2DiscoveredPlugin(
        name="x",
        plugin_type=PluginType.WORKLOAD,
        group=V2_ENTRY_POINT_GROUPS[PluginType.WORKLOAD],
        value="fixture:x",
        distribution=None,
        entry_point=object(),
    )
    result = V2PluginDiscoveryResult(
        plugin=discovered,
        status=V2PluginDiscoveryStatus.DISCOVERED,
    )
    assert result.plugin is discovered
    assert result.descriptor is None
    assert result.error is None


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


def test_lot16_contract_report_manual_incompatible_summary() -> None:
    issue = V2PluginContractIssue(
        code=V2PluginContractIssueCode.API_VERSION,
        message="bad version",
    )
    report = V2PluginContractReport(
        entry_point_name="x",
        entry_point_group=V2_ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        descriptor=None,
        issues=(issue,),
    )
    assert report.summary() == "bad version"
