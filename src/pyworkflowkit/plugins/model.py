"""Stable plugin metadata contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

PLUGIN_API_VERSION = "1"


class PluginType(StrEnum):
    """Extension categories owned by the PyWorkflowKit plugin contract."""

    EXECUTOR = "executor"
    METADATA = "metadata"
    WORKLOAD = "workload"
    EVENT = "event"


@dataclass(frozen=True, slots=True)
class PluginDescriptor:
    """Immutable identity and compatibility metadata for one plugin."""

    name: str
    plugin_type: PluginType
    api_version: str = PLUGIN_API_VERSION
    plugin_version: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("plugin name must not be blank")
        if not isinstance(self.plugin_type, PluginType):
            raise TypeError("plugin_type must be a PluginType")
        if not self.api_version.strip():
            raise ValueError("plugin api_version must not be blank")
        if self.plugin_version is not None and not self.plugin_version.strip():
            raise ValueError("plugin_version must not be blank when provided")
        if self.description is not None and not self.description.strip():
            raise ValueError("plugin description must not be blank when provided")


__all__ = ["PLUGIN_API_VERSION", "PluginDescriptor", "PluginType"]
