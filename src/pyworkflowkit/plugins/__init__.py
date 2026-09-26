"""Plugin foundation for explicit adapter registration."""

from pyworkflowkit.plugins.discovery import (
    ENTRY_POINT_GROUPS,
    DiscoveredPlugin,
    PluginDiscovery,
    PluginDiscoveryReport,
    PluginDiscoveryResult,
    PluginDiscoveryStatus,
)
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
    "ENTRY_POINT_GROUPS",
    "PLUGIN_API_VERSION",
    "DiscoveredPlugin",
    "PluginCatalog",
    "PluginDescriptor",
    "PluginDiscovery",
    "PluginDiscoveryReport",
    "PluginDiscoveryResult",
    "PluginDiscoveryStatus",
    "PluginFactory",
    "PluginRegistry",
    "PluginType",
    "RegisteredPlugin",
]
