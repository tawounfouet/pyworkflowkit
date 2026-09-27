"""Small authoring helpers for independently packaged integrations."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pyworkflowkit.plugins import (
    ENTRY_POINT_GROUPS,
    PLUGIN_API_VERSION,
    PluginDescriptor,
    PluginType,
    RegisteredPlugin,
    assert_plugin_registration_compatible,
)

T = TypeVar("T")


def entry_point_group(plugin_type: PluginType) -> str:
    """Return the frozen Python entry-point group for one plugin category."""

    if not isinstance(plugin_type, PluginType):
        raise TypeError("plugin_type must be a PluginType")
    return ENTRY_POINT_GROUPS[plugin_type]


def plugin_registration(
    *,
    name: str,
    plugin_type: PluginType,
    factory: Callable[[], T],
    plugin_version: str | None = None,
    description: str | None = None,
) -> RegisteredPlugin[T]:
    """Build and self-check one plugin registration using the current Plugin API."""

    registration = RegisteredPlugin(
        descriptor=PluginDescriptor(
            name=name,
            plugin_type=plugin_type,
            api_version=PLUGIN_API_VERSION,
            plugin_version=plugin_version,
            description=description,
        ),
        factory=factory,
    )
    assert_plugin_registration_compatible(
        registration,
        entry_point_name=name,
        entry_point_group=entry_point_group(plugin_type),
    )
    return registration


__all__ = ["entry_point_group", "plugin_registration"]
