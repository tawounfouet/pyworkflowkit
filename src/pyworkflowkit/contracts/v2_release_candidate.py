"""Frozen PyWorkflowKit 2.0 release-candidate compatibility contract.

LOT-22 turns the V2 architecture accumulated by LOT-00 through LOT-21 into an
executable compatibility baseline. Changes to this module after 2.0.0rc1 are RC-reset
events unless they are blocker fixes that preserve the frozen contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

V2_RELEASE_CANDIDATE_CONTRACT_VERSION = "1"
V2_RELEASE_CANDIDATE_VERSION = "2.0.0rc1"
V2_RELEASE_CANDIDATE_TARGET_RELEASE = "2.0.0"
V2_RC_CHANGE_POLICY = "blocker-fixes-only-without-contract-drift"

V2_RC_PUBLIC_SURFACES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "pyworkflowkit": (
            "ExecutionPlan",
            "PyWorkflowKitError",
            "RetryPolicy",
            "TaskAttempt",
            "TaskAttemptId",
            "TaskDefinition",
            "TaskRun",
            "TaskRunId",
            "TimeoutPolicy",
            "WorkflowDefinition",
            "WorkflowResult",
            "WorkflowRun",
            "WorkflowRunId",
            "WorkflowRuntime",
            "__version__",
        ),
        "pyworkflowkit.authoring": (
            "InputDeclaration",
            "OutputDeclaration",
            "RegisteredWorkload",
            "TaskDefinition",
            "WorkflowDefinition",
            "WorkflowDefinitionBuilder",
            "WorkflowTemplate",
            "WorkloadDescriptor",
            "WorkloadPortability",
            "task",
            "workflow",
        ),
        "pyworkflowkit.diagnostics": (
            "Diagnostic",
            "DiagnosticSeverity",
            "FailureCategory",
            "FailureEvidence",
            "OutcomeUncertainty",
            "Retryability",
            "RecoveryAssessment",
            "RecoveryDisposition",
            "RecoveryInspector",
            "RuntimeInspection",
            "RuntimeInspector",
            "TaskInspection",
            "TaskRecoveryAssessment",
        ),
        "pyworkflowkit.executors": (
            "AsyncExecutor",
            "CancellationCapability",
            "CancellationStatus",
            "CancellableExecutor",
            "Executor",
            "ExecutorDescriptor",
            "ExecutorRegistry",
            "InlineExecutor",
            "ProcessExecutor",
            "SubprocessCommand",
            "SubprocessExecutor",
            "SubprocessResult",
            "SubprocessSecurityPolicy",
            "TaskCancellationRequest",
            "TaskCancellationResult",
            "TaskExecutionContext",
            "TaskExecutionRequest",
            "TaskExecutionResult",
            "ThreadExecutor",
            "V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS",
            "V2_EXECUTOR_CONTRACT_VERSION",
            "V2_EXECUTOR_PROTOCOL_METHODS",
            "v2_executor_contract_snapshot",
        ),
        "pyworkflowkit.integrations": (
            "EXTERNAL_WORKLOAD_CONTRACT_VERSION",
            "OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION",
            "REFERENCE_INTEROPERABILITY_CONTRACT_VERSION",
            "ExternalRetryOwner",
            "ExternalWorkload",
            "ExternalWorkloadAdapter",
            "ExternalWorkloadResult",
            "OpenTelemetryBackend",
            "OpenTelemetryMeter",
            "OpenTelemetryTracer",
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
        "pyworkflowkit.lineage": (
            "ExecutionLineage",
            "ExecutionLineageProjector",
            "LineageDependency",
            "MANIFEST_SCHEMA_VERSION",
            "ManifestAttempt",
            "ManifestTaskRun",
            "RunManifest",
            "RunManifestBuilder",
            "TaskExecutionLineage",
        ),
        "pyworkflowkit.persistence": (
            "InMemoryMetadataStore",
            "LegacyMemoryMetadataStore",
            "LegacyMemoryUnitOfWork",
            "LegacyMetadataStore",
            "LegacySQLiteMetadataStore",
            "LegacySQLiteSettings",
            "LegacyUnitOfWork",
            "ManifestReference",
            "MetadataStore",
            "MetadataStoreMetadata",
            "PostgreSQLMetadataStore",
            "PostgreSQLSettings",
            "SQLiteMetadataStore",
            "SQLiteSettings",
            "StateEntityType",
            "StateTransitionRecord",
            "V2_METADATA_STORE_CONTRACT_VERSION",
            "V2_METADATA_STORE_METHODS",
            "create_postgresql_engine",
            "v2_metadata_store_contract_snapshot",
        ),
        "pyworkflowkit.planning": (
            "ExecutionPlan",
            "ExecutorRequirement",
            "TaskPlanEntry",
            "WorkflowPlanner",
        ),
        "pyworkflowkit.plugins": (
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
        ),
        "pyworkflowkit.policies": (
            "BackoffStrategy",
            "FailurePolicy",
            "RetryDecision",
            "RetryEvaluation",
            "RetryEvaluator",
            "RetryJitter",
            "RetryJitterSource",
            "RetryPolicy",
            "SystemRetryJitterSource",
            "TimeoutMode",
            "TimeoutPolicy",
            "V2_TIMEOUT_CONTRACT_VERSION",
            "TriggerRule",
            "V2_RETRY_CONTRACT_VERSION",
            "v2_retry_contract_snapshot",
            "v2_timeout_contract_snapshot",
        ),
        "pyworkflowkit.runtime": (
            "CancellationResult",
            "Clock",
            "CorrelationContext",
            "CorrelationId",
            "ExternalRunRef",
            "ExternalRunObservation",
            "ExternalRunStatus",
            "ExternalRunVerifier",
            "ExternalRunVerifierRegistry",
            "ReconciliationDisposition",
            "ReconciliationReport",
            "ReconciliationService",
            "RuntimeEvent",
            "RuntimeEventType",
            "RetryWaiter",
            "RuntimeIdentityFactory",
            "SystemClock",
            "SystemRetryWaiter",
            "TaskAttempt",
            "TaskAttemptId",
            "TaskOutcome",
            "TaskOutputCheckpoint",
            "TaskReconciliation",
            "TaskRun",
            "TaskRunId",
            "UuidRuntimeIdentityFactory",
            "WorkflowExecutionReference",
            "WorkflowResult",
            "WorkflowRun",
            "WorkflowRunId",
            "WorkflowRuntime",
        ),
        "pyworkflowkit.serialization": (
            "BoundaryContractSpec",
            "BoundaryUpcasterRegistry",
            "BoundaryValue",
            "BoundaryWireCodec",
            "CorrelationContextSchema",
            "DEFAULT_MAX_NESTING_DEPTH",
            "DEFAULT_MAX_PAYLOAD_BYTES",
            "DiagnosticSchema",
            "ExternalRunRefSchema",
            "FailureEvidenceSchema",
            "SchemaCodec",
            "StrictBoundarySchema",
            "StrictSchema",
            "V2_BOUNDARY_WIRE_CONTRACTS",
            "WireContractDescriptor",
            "WireContractError",
            "WireEnvelopeSchema",
            "WorkflowExecutionReferenceSchema",
            "boundary_contract_specs",
            "v2_boundary_wire_contract_snapshot",
        ),
        "pyworkflowkit.states": (
            "BlockReason",
            "SkipReason",
            "TaskAttemptStateMachine",
            "TaskAttemptStatus",
            "TaskRunStateMachine",
            "TaskRunStatus",
            "WorkflowRunStateMachine",
            "WorkflowRunStatus",
        ),
    }
)

V2_RC_STATE_MEMBERS: Mapping[str, tuple[tuple[str, str], ...]] = MappingProxyType(
    {
        "WorkflowRunStatus": (
            ("PENDING", "PENDING"),
            ("RUNNING", "RUNNING"),
            ("SUCCEEDED", "SUCCEEDED"),
            ("FAILED", "FAILED"),
            ("CANCELLATION_REQUESTED", "CANCELLATION_REQUESTED"),
            ("CANCELLED", "CANCELLED"),
            ("TIMED_OUT", "TIMED_OUT"),
            ("UNKNOWN_OUTCOME", "UNKNOWN_OUTCOME"),
        ),
        "TaskRunStatus": (
            ("PENDING", "PENDING"),
            ("READY", "READY"),
            ("RUNNING", "RUNNING"),
            ("SUCCEEDED", "SUCCEEDED"),
            ("FAILED", "FAILED"),
            ("SKIPPED", "SKIPPED"),
            ("CANCELLED", "CANCELLED"),
            ("TIMED_OUT", "TIMED_OUT"),
            ("BLOCKED", "BLOCKED"),
            ("UNKNOWN_OUTCOME", "UNKNOWN_OUTCOME"),
        ),
        "TaskAttemptStatus": (
            ("PENDING", "PENDING"),
            ("STARTING", "STARTING"),
            ("RUNNING", "RUNNING"),
            ("SUCCEEDED", "SUCCEEDED"),
            ("FAILED", "FAILED"),
            ("TIMED_OUT", "TIMED_OUT"),
            ("CANCELLATION_REQUESTED", "CANCELLATION_REQUESTED"),
            ("CANCELLED", "CANCELLED"),
            ("CANCELLATION_UNCONFIRMED", "CANCELLATION_UNCONFIRMED"),
            ("UNKNOWN_OUTCOME", "UNKNOWN_OUTCOME"),
            ("REQUIRES_RECONCILIATION", "REQUIRES_RECONCILIATION"),
        ),
    }
)

V2_RC_IDENTITY_TYPES: tuple[str, ...] = (
    "WorkflowRunId",
    "TaskRunId",
    "TaskAttemptId",
    "CorrelationId",
)

V2_RC_PROTOCOL_METHODS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "Executor": ("descriptor", "execute"),
        "CancellableExecutor": ("cancel",),
        "MetadataStore": (
            "metadata",
            "create_workflow_run",
            "get_workflow_run",
            "update_workflow_run",
            "list_workflow_runs",
            "list_unfinished_workflow_runs",
            "create_task_run",
            "get_task_run",
            "update_task_run",
            "list_task_runs",
            "append_task_attempt",
            "get_task_attempt",
            "update_task_attempt",
            "list_task_attempts",
            "append_external_run_ref",
            "list_external_run_refs",
            "list_state_transitions",
            "list_runtime_events",
            "set_task_output_checkpoint",
            "get_task_output_checkpoint",
            "set_manifest_reference",
            "get_manifest_reference",
        ),
    }
)

V2_RC_WIRE_CONTRACTS: Mapping[str, tuple[str, str, str]] = MappingProxyType(
    {
        "correlation_context": ("pykit.correlation_context", "1", "pykit"),
        "diagnostic": ("pyworkflowkit.diagnostic", "1", "pyworkflowkit"),
        "external_run_ref": ("pyworkflowkit.external_run_ref", "1", "pyworkflowkit"),
        "failure_evidence": ("pykit.failure_evidence", "1", "pykit"),
        "workflow_execution_reference": (
            "pyworkflowkit.workflow_execution_reference",
            "1",
            "pyworkflowkit",
        ),
    }
)

V2_RC_SIBLING_INTEGRATION_CONTRACTS: Mapping[str, str] = MappingProxyType(
    {
        "pyingestkit": "1",
        "pytransformkit": "1",
    }
)

V2_RC_QUALIFICATION_DOMAINS: tuple[str, ...] = (
    "root_api_snapshot",
    "python_matrix",
    "ruff_format_mypy",
    "dag_planning",
    "state_machines",
    "retry_backoff",
    "timeout_cancellation",
    "executor_conformance",
    "metadata_store_conformance",
    "recovery_reconciliation_fault_injection",
    "wire_golden_fixtures",
    "plugin_compatibility",
    "security",
    "sibling_adapter_conformance",
    "optional_extra_isolation",
    "wheel_install",
    "sdist_install",
    "customer_360",
    "migration_fixtures",
    "docs_examples",
    "release_evidence_manifest",
)


def v2_release_candidate_contract_snapshot() -> dict[str, object]:
    """Return deterministic 2.0.0rc1 compatibility and qualification evidence."""

    return {
        "contract_version": V2_RELEASE_CANDIDATE_CONTRACT_VERSION,
        "candidate_version": V2_RELEASE_CANDIDATE_VERSION,
        "target_release": V2_RELEASE_CANDIDATE_TARGET_RELEASE,
        "change_policy": V2_RC_CHANGE_POLICY,
        "public_surfaces": {
            module: list(symbols)
            for module, symbols in sorted(V2_RC_PUBLIC_SURFACES.items())
        },
        "state_members": {
            name: [list(item) for item in members]
            for name, members in sorted(V2_RC_STATE_MEMBERS.items())
        },
        "identity_types": list(V2_RC_IDENTITY_TYPES),
        "protocol_methods": {
            name: list(methods)
            for name, methods in sorted(V2_RC_PROTOCOL_METHODS.items())
        },
        "wire_contracts": {
            name: {
                "contract": contract,
                "contract_version": contract_version,
                "owner": owner,
            }
            for name, (contract, contract_version, owner) in sorted(
                V2_RC_WIRE_CONTRACTS.items()
            )
        },
        "sibling_integration_contracts": dict(
            sorted(V2_RC_SIBLING_INTEGRATION_CONTRACTS.items())
        ),
        "qualification_domains": list(V2_RC_QUALIFICATION_DOMAINS),
    }


__all__ = [
    "V2_RC_CHANGE_POLICY",
    "V2_RC_IDENTITY_TYPES",
    "V2_RC_PROTOCOL_METHODS",
    "V2_RC_PUBLIC_SURFACES",
    "V2_RC_QUALIFICATION_DOMAINS",
    "V2_RC_SIBLING_INTEGRATION_CONTRACTS",
    "V2_RC_STATE_MEMBERS",
    "V2_RC_WIRE_CONTRACTS",
    "V2_RELEASE_CANDIDATE_CONTRACT_VERSION",
    "V2_RELEASE_CANDIDATE_TARGET_RELEASE",
    "V2_RELEASE_CANDIDATE_VERSION",
    "v2_release_candidate_contract_snapshot",
]
