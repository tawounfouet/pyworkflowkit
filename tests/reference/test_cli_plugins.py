"""CLI acceptance for M23 plugin discovery diagnostics."""

from dataclasses import dataclass
import json

from typer.testing import CliRunner

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.cli import app
from pyworkflowkit.plugins import (
    PluginDescriptor,
    PluginType,
    RegisteredPlugin,
)
from pyworkflowkit.plugins.discovery import ENTRY_POINT_GROUPS

runner = CliRunner()


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


def _install_entry_point(monkeypatch):  # type: ignore[no-untyped-def]
    registration = RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="custom",
            plugin_type=PluginType.EXECUTOR,
        ),
        factory=LocalExecutor,
    )
    entry_point = FakeEntryPoint(
        name="custom",
        value="example_plugin:provider",
        group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        provider=lambda: registration,
    )
    monkeypatch.setattr(
        "pyworkflowkit.plugins.discovery.importlib_metadata.entry_points",
        lambda: FakeEntryPoints((entry_point,)),
    )
    return entry_point


def test_plugins_command_discovers_without_loading(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    entry_point = _install_entry_point(monkeypatch)

    result = runner.invoke(app, ["plugins", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["count"] == 1
    assert payload["plugins"][0]["status"] == "discovered"
    assert entry_point.load_calls == 0


def test_doctor_explicit_enablement_loads_plugin(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    entry_point = _install_entry_point(monkeypatch)

    result = runner.invoke(
        app,
        ["doctor", "--enable", "executor:custom", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["healthy"] is True
    assert payload["plugins"][0]["status"] == "loaded"
    assert entry_point.load_calls == 1
