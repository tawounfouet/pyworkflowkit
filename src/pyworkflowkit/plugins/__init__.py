"""Plugin foundation for explicit adapter registration."""

from pyworkflowkit.plugins.model import (
    PLUGIN_API_VERSION,
    PluginDescriptor,
    PluginType,
)
from pyworkflowkit.plugins.registry import (
    PluginCatalog,
    PluginFactory,
    PluginRegistry,
    RegisteredPlugin,
)

__all__ = [
    "PLUGIN_API_VERSION",
    "PluginCatalog",
    "PluginDescriptor",
    "PluginFactory",
    "PluginRegistry",
    "PluginType",
    "RegisteredPlugin",
]
