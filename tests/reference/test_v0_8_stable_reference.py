"""0.8.0 stable ecosystem interoperability reference assertions."""

from __future__ import annotations

from pyworkflowkit.ecosystem import (
    ECOSYSTEM_SDK_CONTRACT_VERSION,
    PluginType,
    assert_plugin_conforms,
    ecosystem_contract_snapshot,
    plugin_registration,
)


class AdapterFactory:
    """Valid generic WORKLOAD plugin that creates an external workload later."""

    def wrap(self) -> object:
        return object()


def test_v0_8_ecosystem_contract_is_stable() -> None:
    snapshot = ecosystem_contract_snapshot()

    assert ECOSYSTEM_SDK_CONTRACT_VERSION == "1"
    assert snapshot["compatibility"] == {
        "series": "0.8-0.9",
        "minimum": "0.8.0b1",
        "maximum_exclusive": "1.0",
    }
    assert snapshot["supported_python_versions"] == ["3.11", "3.12", "3.13"]


def test_v0_8_workload_plugin_category_remains_generic() -> None:
    registration = plugin_registration(
        name="adapter-factory",
        plugin_type=PluginType.WORKLOAD,
        factory=AdapterFactory,
    )

    report = assert_plugin_conforms(
        registration,
        entry_point_name="adapter-factory",
        plugin_type=PluginType.WORKLOAD,
    )

    assert report.compatible is True
