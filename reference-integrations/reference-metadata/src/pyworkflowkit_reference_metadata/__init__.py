"""Independently packaged reference MetadataStore integration."""

from __future__ import annotations

from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.plugins import (
    PLUGIN_API_VERSION,
    PluginDescriptor,
    PluginType,
    RegisteredPlugin,
)


class ReferenceMetadataStore(MemoryMetadataStore):
    """Reference plugin proving MetadataStore packaging/discovery compatibility."""


def plugin() -> RegisteredPlugin[ReferenceMetadataStore]:
    """Return the metadata plugin registration exposed through entry points."""

    return RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="reference-metadata",
            plugin_type=PluginType.METADATA,
            api_version=PLUGIN_API_VERSION,
            plugin_version="0.1.0",
            description="Reference independently packaged MetadataStore plugin.",
        ),
        factory=ReferenceMetadataStore,
    )


__all__ = ["ReferenceMetadataStore", "plugin"]
