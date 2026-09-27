"""M52 unit coverage for the ecosystem authoring SDK."""

from __future__ import annotations

import pytest

from pyworkflowkit.ecosystem import (
    ECOSYSTEM_SDK_CONTRACT_VERSION,
    PluginType,
    RunContext,
    assert_plugin_conforms,
    ecosystem_contract_snapshot,
    entry_point_group,
    plugin_registration,
    validate_plugin_conformance,
)
from pyworkflowkit.errors import PluginCompatibilityError
from pyworkflowkit.integrations import ExternalWorkloadResult


class DirectWorkload:
    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        return ExternalWorkloadResult(
            external_run_id=f"good-{context.task_run_id}",
            succeeded=True,
        )


class WorkloadAdapterFactory:
    """A valid generic WORKLOAD plugin that is not itself an ExternalWorkload."""

    def wrap(self) -> DirectWorkload:
        return DirectWorkload()


class BadEventSink:
    pass


def test_ecosystem_contract_snapshot_freezes_supported_matrix() -> None:
    snapshot = ecosystem_contract_snapshot()

    assert ECOSYSTEM_SDK_CONTRACT_VERSION == "1"
    assert snapshot["sdk_contract_version"] == "1"
    assert snapshot["compatibility"] == {
        "series": "0.8-1.x",
        "minimum": "0.8.0b1",
        "maximum_exclusive": "2.0",
    }
    assert snapshot["supported_python_versions"] == ["3.11", "3.12", "3.13"]
    assert snapshot["contracts"] == {
        "control_plane": "1",
        "external_workload": "1",
        "observability": "1",
        "plugin_api": "1",
        "references": "1",
    }
    assert snapshot["entry_point_groups"] == {
        "event": "pyworkflowkit.events",
        "executor": "pyworkflowkit.executors",
        "metadata": "pyworkflowkit.metadata",
        "workload": "pyworkflowkit.workloads",
    }


def test_authoring_helper_builds_self_consistent_registration() -> None:
    registration = plugin_registration(
        name="good-workload",
        plugin_type=PluginType.WORKLOAD,
        factory=DirectWorkload,
        plugin_version="1.2.3",
    )

    assert registration.descriptor.name == "good-workload"
    assert registration.descriptor.api_version == "1"
    assert registration.descriptor.plugin_version == "1.2.3"
    assert entry_point_group(PluginType.WORKLOAD) == "pyworkflowkit.workloads"

    report = assert_plugin_conforms(
        registration,
        entry_point_name="good-workload",
        plugin_type=PluginType.WORKLOAD,
    )
    assert report.compatible


def test_workload_plugin_conformance_preserves_generic_adapter_factory_shape() -> None:
    registration = plugin_registration(
        name="adapter-factory",
        plugin_type=PluginType.WORKLOAD,
        factory=WorkloadAdapterFactory,
    )

    report = validate_plugin_conformance(
        registration,
        entry_point_name="adapter-factory",
        plugin_type=PluginType.WORKLOAD,
    )

    assert report.compatible is True
    assert isinstance(registration.create().wrap(), DirectWorkload)


def test_validate_conformance_reports_bad_typed_plugin_without_raising() -> None:
    registration = plugin_registration(
        name="bad-event",
        plugin_type=PluginType.EVENT,
        factory=BadEventSink,
    )

    report = validate_plugin_conformance(
        registration,
        entry_point_name="bad-event",
        plugin_type=PluginType.EVENT,
    )

    assert report.compatible is False
    assert report.messages == ("event plugin instance does not satisfy RuntimeEventSink",)


def test_assert_conformance_raises_public_compatibility_error() -> None:
    registration = plugin_registration(
        name="bad-event",
        plugin_type=PluginType.EVENT,
        factory=BadEventSink,
    )

    with pytest.raises(PluginCompatibilityError):
        assert_plugin_conforms(
            registration,
            entry_point_name="bad-event",
            plugin_type=PluginType.EVENT,
        )


def test_entry_point_group_rejects_non_plugin_type() -> None:
    with pytest.raises(TypeError):
        entry_point_group("workload")  # type: ignore[arg-type]
