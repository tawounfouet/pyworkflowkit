"""Public SDK facade for third-party PyWorkflowKit integrations."""

from pyworkflowkit.control_plane import ControlPlaneProvider, WorkflowRuntimeProvider
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef, TaskResult
from pyworkflowkit.ecosystem.authoring import entry_point_group, plugin_registration
from pyworkflowkit.ecosystem.conformance import (
    EcosystemConformanceReport,
    assert_plugin_conforms,
    validate_plugin_conformance,
)
from pyworkflowkit.ecosystem.contracts import (
    ECOSYSTEM_COMPATIBILITY_SERIES,
    ECOSYSTEM_MAXIMUM_EXCLUSIVE_VERSION,
    ECOSYSTEM_MINIMUM_VERSION,
    ECOSYSTEM_SDK_CONTRACT_VERSION,
    ecosystem_contract_snapshot,
)
from pyworkflowkit.integrations import (
    ExternalRetryOwner,
    ExternalWorkload,
    ExternalWorkloadAdapter,
    ExternalWorkloadResult,
    RuntimeTelemetrySink,
    TelemetryBackend,
    external_workload_task,
)
from pyworkflowkit.plugins import (
    ENTRY_POINT_GROUPS,
    PLUGIN_API_VERSION,
    PluginCatalog,
    PluginDescriptor,
    PluginDiscovery,
    PluginDiscoveryReport,
    PluginDiscoveryStatus,
    PluginType,
    RegisteredPlugin,
)
from pyworkflowkit.ports.executor import Executor, ExecutorCapabilities, RunContext
from pyworkflowkit.ports.metadata_store import MetadataStore, UnitOfWork
from pyworkflowkit.ports.observability import RuntimeEventSink

__all__ = [
    "ECOSYSTEM_COMPATIBILITY_SERIES",
    "ECOSYSTEM_MAXIMUM_EXCLUSIVE_VERSION",
    "ECOSYSTEM_MINIMUM_VERSION",
    "ECOSYSTEM_SDK_CONTRACT_VERSION",
    "ENTRY_POINT_GROUPS",
    "PLUGIN_API_VERSION",
    "ArtifactReference",
    "ControlPlaneProvider",
    "EcosystemConformanceReport",
    "Executor",
    "ExecutorCapabilities",
    "ExternalRetryOwner",
    "ExternalRunRef",
    "ExternalWorkload",
    "ExternalWorkloadAdapter",
    "ExternalWorkloadResult",
    "MetadataStore",
    "PluginCatalog",
    "PluginDescriptor",
    "PluginDiscovery",
    "PluginDiscoveryReport",
    "PluginDiscoveryStatus",
    "PluginType",
    "RegisteredPlugin",
    "RunContext",
    "RuntimeEventSink",
    "RuntimeTelemetrySink",
    "TaskResult",
    "TelemetryBackend",
    "UnitOfWork",
    "WorkflowRuntimeProvider",
    "assert_plugin_conforms",
    "ecosystem_contract_snapshot",
    "entry_point_group",
    "external_workload_task",
    "plugin_registration",
    "validate_plugin_conformance",
]
