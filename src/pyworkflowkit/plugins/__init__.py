"""Plugin foundation for explicit adapter registration."""

from pyworkflowkit.plugins.contracts import (
    ENTRY_POINT_GROUPS,
    PLUGIN_TYPE_BY_ENTRY_POINT_GROUP,
    PluginContractIssue,
    PluginContractIssueCode,
    PluginContractReport,
    PluginInstanceContractReport,
    assert_plugin_instance_compatible,
    assert_plugin_registration_compatible,
    validate_plugin_instance,
    validate_plugin_registration,
)
from pyworkflowkit.plugins.discovery import (
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
    "PLUGIN_TYPE_BY_ENTRY_POINT_GROUP",
    "DiscoveredPlugin",
    "PluginCatalog",
    "PluginContractIssue",
    "PluginContractIssueCode",
    "PluginContractReport",
    "PluginDescriptor",
    "PluginDiscovery",
    "PluginDiscoveryReport",
    "PluginDiscoveryResult",
    "PluginDiscoveryStatus",
    "PluginFactory",
    "PluginInstanceContractReport",
    "PluginRegistry",
    "PluginType",
    "RegisteredPlugin",
    "assert_plugin_instance_compatible",
    "assert_plugin_registration_compatible",
    "validate_plugin_instance",
    "validate_plugin_registration",
]
