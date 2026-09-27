"""Machine-readable public API freeze for the PyWorkflowKit 1.0 stabilization line.

This module does not make every importable implementation module public. It records only
the facades that PyWorkflowKit intentionally treats as compatibility surfaces on the path
to 1.0.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

PUBLIC_API_CONTRACT_VERSION = "1"
PUBLIC_API_TARGET_RELEASE = "1.0.0"

PUBLIC_API_SURFACES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "pyworkflowkit": (
            "ArtifactId",
            "ArtifactReference",
            "BackoffStrategy",
            "ExternalRunRef",
            "ExternalRunRefId",
            "FailurePolicy",
            "PyWorkflowKitError",
            "RetryPolicy",
            "RunContext",
            "RuntimeSettings",
            "TaskDefinition",
            "TaskHandle",
            "TaskId",
            "TaskResult",
            "TimeoutMode",
            "WorkflowBuilder",
            "WorkflowDefinition",
            "WorkflowId",
            "WorkflowParameter",
            "WorkflowRuntime",
            "__version__",
            "task",
            "workflow",
        ),
        "pyworkflowkit.control_plane": (
            "CONTROL_PLANE_OPERATIONS",
            "CONTROL_PLANE_PROVIDER_CONTRACT_VERSION",
            "ControlPlaneCapabilityError",
            "ControlPlaneOperation",
            "ControlPlaneProvider",
            "ControlPlaneProviderError",
            "ControlPlaneRunSchema",
            "ExecutionGroupSchema",
            "ExecutionLineageSchema",
            "ExternalRunObservationSchema",
            "LineageDependencySchema",
            "ProviderCapabilitiesSchema",
            "ReconciliationReportSchema",
            "RecoveryAssessmentSchema",
            "TaskExecutionLineageSchema",
            "TaskIdempotencySchema",
            "TaskReconciliationSchema",
            "WorkflowInspectionSchema",
            "WorkflowRuntimeProvider",
            "WorkflowValidationResultSchema",
        ),
        "pyworkflowkit.ecosystem": (
            "ArtifactReference",
            "CancellationCapability",
            "ControlPlaneProvider",
            "ECOSYSTEM_COMPATIBILITY_SERIES",
            "ECOSYSTEM_MAXIMUM_EXCLUSIVE_VERSION",
            "ECOSYSTEM_MINIMUM_VERSION",
            "ECOSYSTEM_SDK_CONTRACT_VERSION",
            "ENTRY_POINT_GROUPS",
            "EcosystemConformanceReport",
            "Executor",
            "ExecutorCapabilities",
            "ExternalRetryOwner",
            "ExternalRunRef",
            "ExternalWorkload",
            "ExternalWorkloadAdapter",
            "ExternalWorkloadResult",
            "MetadataStore",
            "PLUGIN_API_VERSION",
            "PluginCatalog",
            "PluginDescriptor",
            "PluginDiscovery",
            "PluginDiscoveryReport",
            "PluginDiscoveryStatus",
            "PluginType",
            "RegisteredPlugin",
            "RunContext",
            "RuntimeEvent",
            "RuntimeEventSink",
            "RuntimeTelemetrySink",
            "TaskAttempt",
            "TaskDefinition",
            "TaskHandler",
            "TaskResult",
            "TaskRun",
            "TaskRunId",
            "TelemetryBackend",
            "TimeoutCapability",
            "UnitOfWork",
            "WorkflowRun",
            "WorkflowRunId",
            "WorkflowRuntimeProvider",
            "assert_plugin_conforms",
            "ecosystem_contract_snapshot",
            "entry_point_group",
            "external_workload_task",
            "plugin_registration",
            "validate_plugin_conformance",
        ),
        "pyworkflowkit.integrations": (
            "EXTERNAL_WORKLOAD_CONTRACT_VERSION",
            "ExternalRetryOwner",
            "ExternalWorkload",
            "ExternalWorkloadAdapter",
            "ExternalWorkloadResult",
            "OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION",
            "OpenTelemetryBackend",
            "OpenTelemetryMeter",
            "OpenTelemetryTracer",
            "REFERENCE_INTEROPERABILITY_CONTRACT_VERSION",
            "RuntimeTelemetryProjector",
            "RuntimeTelemetrySink",
            "TelemetryBackend",
            "TelemetryCorrelation",
            "TelemetryEvent",
            "TelemetryMetric",
            "TelemetryMetricKind",
            "TelemetryProjection",
            "external_workload_task",
            "normalize_reference_metadata",
            "validate_portable_artifact_reference",
            "validate_portable_external_run_ref",
            "validate_provider_name",
            "validate_reference_uri",
        ),
        "pyworkflowkit.plugins": (
            "DiscoveredPlugin",
            "ENTRY_POINT_GROUPS",
            "PLUGIN_API_VERSION",
            "PLUGIN_TYPE_BY_ENTRY_POINT_GROUP",
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
        ),
        "pyworkflowkit.public_api": (
            "PUBLIC_API_CONTRACT_VERSION",
            "PUBLIC_API_SURFACES",
            "PUBLIC_API_TARGET_RELEASE",
            "public_api_contract_snapshot",
        ),
    }
)


def public_api_contract_snapshot() -> dict[str, object]:
    """Return a deterministic JSON-serializable description of the frozen public facades."""

    return {
        "contract_version": PUBLIC_API_CONTRACT_VERSION,
        "target_release": PUBLIC_API_TARGET_RELEASE,
        "surfaces": {
            module_name: list(symbols)
            for module_name, symbols in sorted(PUBLIC_API_SURFACES.items())
        },
    }


__all__ = [
    "PUBLIC_API_CONTRACT_VERSION",
    "PUBLIC_API_SURFACES",
    "PUBLIC_API_TARGET_RELEASE",
    "public_api_contract_snapshot",
]
