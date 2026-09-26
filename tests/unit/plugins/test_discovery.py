"""Tests for opt-in entry-point plugin discovery."""

from __future__ import annotations

from dataclasses import dataclass

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.plugins import (
    PLUGIN_API_VERSION,
    PluginCatalog,
    PluginDescriptor,
    PluginType,
    RegisteredPlugin,
)
from pyworkflowkit.plugins.discovery import (
    ENTRY_POINT_GROUPS,
    PluginDiscovery,
    PluginDiscoveryStatus,
)


@dataclass
class FakeEntryPoint:
    name: str
    value: str
    group: str
    loaded: object
    load_calls: int = 0

    @property
    def dist(self):  # type: ignore[no-untyped-def]
        return None

    def load(self) -> object:
        self.load_calls += 1
        return self.loaded


class FakeEntryPoints(tuple):
    def select(self, *, group: str):  # type: ignore[no-untyped-def]
        return FakeEntryPoints(value for value in self if value.group == group)


def _registration(
    *,
    name: str = "custom",
    api_version: str = PLUGIN_API_VERSION,
) -> RegisteredPlugin[LocalExecutor]:
    return RegisteredPlugin(
        descriptor=PluginDescriptor(
            name=name,
            plugin_type=PluginType.EXECUTOR,
            api_version=api_version,
        ),
        factory=LocalExecutor,
    )


def test_discovery_does_not_import_plugin_code(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    entry_point = FakeEntryPoint(
        name="custom",
        value="package:provider",
        group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        loaded=lambda: _registration(),
    )
    monkeypatch.setattr(
        "pyworkflowkit.plugins.discovery.importlib_metadata.entry_points",
        lambda: FakeEntryPoints((entry_point,)),
    )

    plugins = PluginDiscovery().discover()

    assert plugins[0].name == "custom"
    assert entry_point.load_calls == 0


def test_only_explicitly_enabled_plugin_is_loaded(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    enabled_entry_point = FakeEntryPoint(
        name="enabled",
        value="package:enabled",
        group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        loaded=lambda: _registration(name="enabled"),
    )
    disabled_entry_point = FakeEntryPoint(
        name="disabled",
        value="package:disabled",
        group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        loaded=lambda: _registration(name="disabled"),
    )
    monkeypatch.setattr(
        "pyworkflowkit.plugins.discovery.importlib_metadata.entry_points",
        lambda: FakeEntryPoints((enabled_entry_point, disabled_entry_point)),
    )

    catalog = PluginCatalog()
    report = PluginDiscovery().enable_selected(
        catalog=catalog,
        enabled={PluginType.EXECUTOR: ("enabled",)},
    )

    statuses = {result.plugin.name: result.status for result in report.results}

    assert statuses == {
        "disabled": PluginDiscoveryStatus.DISCOVERED,
        "enabled": PluginDiscoveryStatus.LOADED,
    }
    assert enabled_entry_point.load_calls == 1
    assert disabled_entry_point.load_calls == 0
    assert isinstance(catalog.executors.create("enabled"), LocalExecutor)


def test_incompatible_api_version_is_reported_without_registration(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    entry_point = FakeEntryPoint(
        name="custom",
        value="package:provider",
        group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        loaded=lambda: _registration(api_version="999"),
    )
    monkeypatch.setattr(
        "pyworkflowkit.plugins.discovery.importlib_metadata.entry_points",
        lambda: FakeEntryPoints((entry_point,)),
    )

    catalog = PluginCatalog()
    report = PluginDiscovery().enable_selected(
        catalog=catalog,
        enabled={PluginType.EXECUTOR: ("custom",)},
    )

    assert report.has_errors is True
    assert report.results[0].status is PluginDiscoveryStatus.INCOMPATIBLE
    assert "custom" not in catalog.executors


def test_provider_failure_is_isolated_in_report(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def broken_provider() -> object:
        raise RuntimeError("boom")

    entry_point = FakeEntryPoint(
        name="broken",
        value="package:provider",
        group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        loaded=broken_provider,
    )
    monkeypatch.setattr(
        "pyworkflowkit.plugins.discovery.importlib_metadata.entry_points",
        lambda: FakeEntryPoints((entry_point,)),
    )

    report = PluginDiscovery().enable_selected(
        catalog=PluginCatalog(),
        enabled={PluginType.EXECUTOR: ("broken",)},
    )

    assert report.has_errors is True
    assert report.results[0].status is PluginDiscoveryStatus.FAILED
    assert "boom" in (report.results[0].error or "")
