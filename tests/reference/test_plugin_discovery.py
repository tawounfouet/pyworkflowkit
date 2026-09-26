"""M23 entry-point discovery acceptance coverage."""

from dataclasses import dataclass

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.plugins import PluginCatalog, PluginDescriptor, PluginType, RegisteredPlugin
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
    provider: object
    load_calls: int = 0

    @property
    def dist(self):  # type: ignore[no-untyped-def]
        return None

    def load(self) -> object:
        self.load_calls += 1
        return self.provider


class FakeEntryPoints(tuple):
    def select(self, *, group: str):  # type: ignore[no-untyped-def]
        return FakeEntryPoints(value for value in self if value.group == group)


def test_discover_then_explicitly_enable_executor_plugin(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    registration = RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="reference",
            plugin_type=PluginType.EXECUTOR,
        ),
        factory=LocalExecutor,
    )
    entry_point = FakeEntryPoint(
        name="reference",
        value="reference_plugin:provider",
        group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        provider=lambda: registration,
    )
    monkeypatch.setattr(
        "pyworkflowkit.plugins.discovery.importlib_metadata.entry_points",
        lambda: FakeEntryPoints((entry_point,)),
    )

    discovery = PluginDiscovery()
    candidates = discovery.discover()

    assert len(candidates) == 1
    assert entry_point.load_calls == 0

    catalog = PluginCatalog()
    report = discovery.enable_selected(
        catalog=catalog,
        enabled={PluginType.EXECUTOR: ("reference",)},
    )

    assert report.results[0].status is PluginDiscoveryStatus.LOADED
    assert entry_point.load_calls == 1
    assert catalog.executors.create("reference").key == "local"
