"""Unit tests for the M44 public plugin compatibility contract suite."""

from __future__ import annotations

from typing import Any, cast

import pytest

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.domain.runtime import RuntimeEvent
from pyworkflowkit.errors import PluginCompatibilityError
from pyworkflowkit.plugins import (
    ENTRY_POINT_GROUPS,
    PLUGIN_API_VERSION,
    PLUGIN_TYPE_BY_ENTRY_POINT_GROUP,
    PluginContractIssueCode,
    PluginDescriptor,
    PluginType,
    RegisteredPlugin,
    assert_plugin_instance_compatible,
    assert_plugin_registration_compatible,
    validate_plugin_instance,
    validate_plugin_registration,
)


def _executor_registration(
    *,
    name: str = "sample",
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


def test_entry_point_groups_have_deterministic_reverse_mapping() -> None:
    for plugin_type, group in ENTRY_POINT_GROUPS.items():
        assert PLUGIN_TYPE_BY_ENTRY_POINT_GROUP[group] is plugin_type


def test_registration_validation_does_not_invoke_factory() -> None:
    created = 0

    def factory() -> LocalExecutor:
        nonlocal created
        created += 1
        return LocalExecutor()

    registration = RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="sample",
            plugin_type=PluginType.EXECUTOR,
        ),
        factory=factory,
    )

    report = validate_plugin_registration(
        registration,
        entry_point_name="sample",
        entry_point_group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
    )

    assert report.compatible is True
    assert report.issues == ()
    assert created == 0
    assert "compatible with PyWorkflowKit plugin API" in report.summary()


def test_registration_report_collects_name_type_and_api_issues() -> None:
    registration = RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="wrong-name",
            plugin_type=PluginType.EVENT,
            api_version="999",
        ),
        factory=LocalExecutor,
    )

    report = validate_plugin_registration(
        registration,
        entry_point_name="sample",
        entry_point_group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
    )

    assert report.compatible is False
    assert {issue.code for issue in report.issues} == {
        PluginContractIssueCode.DESCRIPTOR_NAME,
        PluginContractIssueCode.DESCRIPTOR_TYPE,
        PluginContractIssueCode.API_VERSION,
    }
    assert "descriptor name" in report.summary()


def test_unknown_entry_point_group_is_reported() -> None:
    report = validate_plugin_registration(
        _executor_registration(),
        entry_point_name="sample",
        entry_point_group="pyworkflowkit.unknown",
    )

    assert report.compatible is False
    assert report.plugin_type is None
    assert report.issues[0].code is PluginContractIssueCode.ENTRY_POINT_GROUP


def test_non_registration_provider_result_is_reported() -> None:
    report = validate_plugin_registration(
        object(),
        entry_point_name="sample",
        entry_point_group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
    )

    assert report.compatible is False
    assert report.descriptor is None
    assert PluginContractIssueCode.REGISTRATION_TYPE in {issue.code for issue in report.issues}


def test_non_callable_factory_is_reported_without_invocation() -> None:
    registration = RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="sample",
            plugin_type=PluginType.EXECUTOR,
        ),
        factory=cast(Any, 42),
    )

    report = validate_plugin_registration(
        registration,
        entry_point_name="sample",
        entry_point_group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
    )

    assert report.compatible is False
    assert report.issues[-1].code is PluginContractIssueCode.FACTORY


def test_assertion_helper_raises_public_compatibility_error() -> None:
    with pytest.raises(PluginCompatibilityError, match="API version"):
        assert_plugin_registration_compatible(
            _executor_registration(api_version="999"),
            entry_point_name="sample",
            entry_point_group=ENTRY_POINT_GROUPS[PluginType.EXECUTOR],
        )


def test_executor_instance_conformance_is_runtime_checkable() -> None:
    compatible = validate_plugin_instance(
        LocalExecutor(),
        plugin_type=PluginType.EXECUTOR,
    )
    incompatible = validate_plugin_instance(
        object(),
        plugin_type=PluginType.EXECUTOR,
    )

    assert compatible.compatible is True
    assert "satisfies plugin API" in compatible.summary()
    assert incompatible.compatible is False
    assert incompatible.issues[0].code is PluginContractIssueCode.INSTANCE_TYPE
    assert "Executor" in incompatible.summary()


def test_metadata_and_event_instance_contracts_are_runtime_checkable() -> None:
    class Sink:
        @property
        def name(self) -> str:
            return "sink"

        def emit(self, event: RuntimeEvent) -> None:
            del event

    assert validate_plugin_instance(
        MemoryMetadataStore(),
        plugin_type=PluginType.METADATA,
    ).compatible
    assert validate_plugin_instance(
        Sink(),
        plugin_type=PluginType.EVENT,
    ).compatible


def test_assert_instance_helper_rejects_structural_mismatch() -> None:
    with pytest.raises(PluginCompatibilityError, match="Executor"):
        assert_plugin_instance_compatible(
            object(),
            plugin_type=PluginType.EXECUTOR,
        )


def test_validate_instance_rejects_non_plugin_type_argument() -> None:
    with pytest.raises(TypeError, match="PluginType"):
        validate_plugin_instance(
            object(),
            plugin_type=cast(Any, "executor"),
        )


def test_workload_instance_contract_remains_generic_in_api_v1() -> None:
    report = assert_plugin_instance_compatible(
        object(),
        plugin_type=PluginType.WORKLOAD,
    )

    assert report.compatible is True
