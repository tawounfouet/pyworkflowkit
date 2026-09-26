"""Tests for the M22 manual plugin foundation."""

import pytest

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.errors import (
    DuplicatePluginError,
    PluginNotFoundError,
    PluginTypeMismatchError,
)
from pyworkflowkit.plugins import (
    PLUGIN_API_VERSION,
    PluginCatalog,
    PluginDescriptor,
    PluginRegistry,
    PluginType,
)
from pyworkflowkit.ports.executor import Executor


def test_descriptor_defaults_to_current_plugin_api_version() -> None:
    descriptor = PluginDescriptor(
        name="local-alt",
        plugin_type=PluginType.EXECUTOR,
    )

    assert descriptor.api_version == PLUGIN_API_VERSION


def test_typed_registry_manually_registers_and_creates_plugin() -> None:
    registry: PluginRegistry[Executor] = PluginRegistry(
        plugin_type=PluginType.EXECUTOR
    )
    descriptor = PluginDescriptor(
        name="local-alt",
        plugin_type=PluginType.EXECUTOR,
        plugin_version="1.0.0",
    )

    registry.register(descriptor, LocalExecutor)

    instance = registry.create("local-alt")

    assert isinstance(instance, LocalExecutor)
    assert registry.descriptors() == (descriptor,)


def test_duplicate_manual_registration_is_rejected() -> None:
    registry: PluginRegistry[Executor] = PluginRegistry(
        plugin_type=PluginType.EXECUTOR
    )
    descriptor = PluginDescriptor(
        name="local-alt",
        plugin_type=PluginType.EXECUTOR,
    )
    registry.register(descriptor, LocalExecutor)

    with pytest.raises(DuplicatePluginError):
        registry.register(descriptor, LocalExecutor)


def test_registry_rejects_wrong_plugin_type() -> None:
    registry: PluginRegistry[Executor] = PluginRegistry(
        plugin_type=PluginType.EXECUTOR
    )
    descriptor = PluginDescriptor(
        name="wrong",
        plugin_type=PluginType.METADATA,
    )

    with pytest.raises(PluginTypeMismatchError):
        registry.register(descriptor, LocalExecutor)


def test_missing_plugin_raises_public_error() -> None:
    registry: PluginRegistry[Executor] = PluginRegistry(
        plugin_type=PluginType.EXECUTOR
    )

    with pytest.raises(PluginNotFoundError):
        registry.create("missing")


def test_catalog_keeps_registries_separate_and_sorted() -> None:
    catalog = PluginCatalog()
    catalog.workloads.register(
        PluginDescriptor(name="zeta", plugin_type=PluginType.WORKLOAD),
        object,
    )
    catalog.events.register(
        PluginDescriptor(name="alpha", plugin_type=PluginType.EVENT),
        object,
    )
    catalog.executors.register(
        PluginDescriptor(name="local-alt", plugin_type=PluginType.EXECUTOR),
        LocalExecutor,
    )

    assert [
        (descriptor.plugin_type.value, descriptor.name)
        for descriptor in catalog.descriptors()
    ] == [
        ("event", "alpha"),
        ("executor", "local-alt"),
        ("workload", "zeta"),
    ]
