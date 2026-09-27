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


class GoodWorkload:
    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        return ExternalWorkloadResult(
            external_run_id=f"good-{context.task_run_id}",
            succeeded=True,
        )


class BadWorkload:
    pass


def test_ecosystem_contract_snapshot_freezes_supported_matrix() -> None:
    snapshot = ecosystem_contract_snapshot()

    assert ECOSYSTEM_SDK_CONTRACT_VERSION == "1"
    assert snapshot["sdk_contract_version"] == "1"
    assert snapshot["compatibility"] == {
        "series": "0.8",
        "minimum": "0.8.0b1",
        "maximum_exclusive": "0.9",
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
        factory=GoodWorkload,
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


def test_validate_conformance_reports_bad_workload_without_raising() -> None:
    registration = plugin_registration(
        name="bad-workload",
        plugin_type=PluginType.WORKLOAD,
        factory=BadWorkload,
    )

    report = validate_plugin_conformance(
        registration,
        entry_point_name="bad-workload",
        plugin_type=PluginType.WORKLOAD,
    )

    assert report.compatible is False
    assert report.messages == ("workload plugin instance does not satisfy ExternalWorkload",)


def test_assert_conformance_raises_public_compatibility_error() -> None:
    registration = plugin_registration(
        name="bad-workload",
        plugin_type=PluginType.WORKLOAD,
        factory=BadWorkload,
    )

    with pytest.raises(PluginCompatibilityError):
        assert_plugin_conforms(
            registration,
            entry_point_name="bad-workload",
            plugin_type=PluginType.WORKLOAD,
        )


def test_entry_point_group_rejects_non_plugin_type() -> None:
    with pytest.raises(TypeError):
        entry_point_group("workload")  # type: ignore[arg-type]
