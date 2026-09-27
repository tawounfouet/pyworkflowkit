"""M44 reference acceptance for third-party plugin compatibility."""

from __future__ import annotations

from dataclasses import fields

import pytest

from pyworkflowkit.adapters.executors.local import LocalExecutor
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
    validate_plugin_registration,
)


def third_party_plugin() -> RegisteredPlugin[LocalExecutor]:
    """Represent a provider function living in an external distribution."""

    return RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="third-party",
            plugin_type=PluginType.EXECUTOR,
            api_version=PLUGIN_API_VERSION,
            plugin_version="1.2.0",
            description="Third-party contract fixture",
        ),
        factory=LocalExecutor,
    )


def test_m44_plugin_api_v1_categories_groups_and_descriptor_shape_are_frozen() -> None:
    assert PLUGIN_API_VERSION == "1"
    assert tuple(item.value for item in PluginType) == (
        "executor",
        "metadata",
        "workload",
        "event",
    )
    assert dict(ENTRY_POINT_GROUPS) == {
        PluginType.EXECUTOR: "pyworkflowkit.executors",
        PluginType.METADATA: "pyworkflowkit.metadata",
        PluginType.WORKLOAD: "pyworkflowkit.workloads",
        PluginType.EVENT: "pyworkflowkit.events",
    }
    assert dict(PLUGIN_TYPE_BY_ENTRY_POINT_GROUP) == {
        "pyworkflowkit.executors": PluginType.EXECUTOR,
        "pyworkflowkit.metadata": PluginType.METADATA,
        "pyworkflowkit.workloads": PluginType.WORKLOAD,
        "pyworkflowkit.events": PluginType.EVENT,
    }
    assert tuple(field.name for field in fields(PluginDescriptor)) == (
        "name",
        "plugin_type",
        "api_version",
        "plugin_version",
        "description",
    )


def test_m44_external_author_can_validate_registration_without_loading_metadata() -> None:
    registration = third_party_plugin()

    report = assert_plugin_registration_compatible(
        registration,
        entry_point_name="third-party",
        entry_point_group="pyworkflowkit.executors",
    )

    assert report.compatible is True
    assert report.descriptor == registration.descriptor
    assert report.plugin_type is PluginType.EXECUTOR


def test_m44_external_author_can_explicitly_validate_created_instance() -> None:
    registration = third_party_plugin()

    report = assert_plugin_instance_compatible(
        registration.create(),
        plugin_type=PluginType.EXECUTOR,
    )

    assert report.compatible is True


def test_m44_api_mismatch_is_machine_diagnosable_and_publicly_rejected() -> None:
    registration = RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="third-party",
            plugin_type=PluginType.EXECUTOR,
            api_version="2",
        ),
        factory=LocalExecutor,
    )

    report = validate_plugin_registration(
        registration,
        entry_point_name="third-party",
        entry_point_group="pyworkflowkit.executors",
    )

    assert report.compatible is False
    assert PluginContractIssueCode.API_VERSION in {
        issue.code for issue in report.issues
    }

    with pytest.raises(PluginCompatibilityError):
        assert_plugin_registration_compatible(
            registration,
            entry_point_name="third-party",
            entry_point_group="pyworkflowkit.executors",
        )


def test_m44_issue_codes_are_frozen_for_external_test_automation() -> None:
    assert tuple(item.value for item in PluginContractIssueCode) == (
        "registration_type",
        "entry_point_group",
        "descriptor_name",
        "descriptor_type",
        "api_version",
        "factory",
        "instance_type",
    )
