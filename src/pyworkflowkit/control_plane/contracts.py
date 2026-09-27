"""Portable control-plane contracts for PyWorkflowKit."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pyworkflowkit.contracts.serialization import (
    RuntimeEventSchema,
    StrictSchema,
    WorkflowDefinitionSchema,
)

CONTROL_PLANE_PROVIDER_CONTRACT_VERSION = "1"


class ControlPlaneOperation(StrEnum):
    """Stable operation identifiers exposed by control-plane providers."""

    VALIDATE_WORKFLOW = "validate_workflow"
    INSPECT_WORKFLOW = "inspect_workflow"
    EXECUTE_WORKFLOW = "execute_workflow"
    INSPECT_RUN = "inspect_run"
    LIST_RUNTIME_EVENTS = "list_runtime_events"
    RETRIEVE_MANIFEST = "retrieve_manifest"
    RETRIEVE_LINEAGE = "retrieve_lineage"
    REQUEST_CANCELLATION = "request_cancellation"
    ASSESS_RECOVERY = "assess_recovery"
    RECONCILE_RUN = "reconcile_run"
    RESUME_RUN = "resume_run"
    INSPECT_CAPABILITIES = "inspect_capabilities"


CONTROL_PLANE_OPERATIONS = tuple(operation.value for operation in ControlPlaneOperation)


class ProviderCapabilitiesSchema(StrictSchema):
    """Portable capability declaration for one provider instance."""

    contract_version: str
    provider_name: str
    runtime_version: str
    operations: dict[str, bool]
    scheduling_owned_by_control_plane: bool = True
    background_execution: bool = False


class WorkflowValidationResultSchema(StrictSchema):
    """Portable workflow validation result."""

    valid: bool
    workflow_id: str | None = None
    workflow_version: str | None = None
    task_count: int = 0
    diagnostics: tuple[str, ...] = ()


class ExecutionGroupSchema(StrictSchema):
    """One deterministic topological execution group."""

    index: int
    task_ids: tuple[str, ...]


class WorkflowInspectionSchema(StrictSchema):
    """Portable static workflow inspection."""

    definition: WorkflowDefinitionSchema
    task_order: tuple[str, ...]
    groups: tuple[ExecutionGroupSchema, ...]


class ControlPlaneRunSchema(StrictSchema):
    """Portable run summary that deliberately excludes raw workflow parameters."""

    run_id: str
    workflow_id: str
    workflow_version: str
    status: str
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class LineageDependencySchema(StrictSchema):
    upstream_task_run_id: str
    downstream_task_run_id: str


class TaskExecutionLineageSchema(StrictSchema):
    task_id: str
    task_run_id: str
    attempt_ids: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    external_ref_ids: tuple[str, ...] = ()


class ExecutionLineageSchema(StrictSchema):
    run_id: str
    workflow_id: str
    workflow_version: str
    tasks: tuple[TaskExecutionLineageSchema, ...]
    dependencies: tuple[LineageDependencySchema, ...]


class TaskIdempotencySchema(StrictSchema):
    task_id: str
    task_run_id: str
    idempotency_key: str
    attempt_count: int


class RecoveryAssessmentSchema(StrictSchema):
    run_id: str
    workflow_id: str
    workflow_version: str
    workflow_status: str
    observed_at: datetime
    last_evidence_at: datetime | None
    stale_after_seconds: float
    liveness: str
    resume_eligibility: str
    running_task_run_ids: tuple[str, ...]
    running_attempt_ids: tuple[str, ...]
    retry_waiting_task_run_ids: tuple[str, ...]
    next_retry_eligible_at: datetime | None
    external_run_ref_count: int
    unresolved_external_run_ref_count: int
    idempotency: tuple[TaskIdempotencySchema, ...]
    reasons: tuple[str, ...]


class ExternalRunObservationSchema(StrictSchema):
    external_ref_id: str
    provider: str
    external_run_id: str
    status: str
    reason: str | None = None


class TaskReconciliationSchema(StrictSchema):
    task_run_id: str
    task_id: str
    disposition: str
    running_attempt_ids: tuple[str, ...]
    observations: tuple[ExternalRunObservationSchema, ...]
    reasons: tuple[str, ...]


class ReconciliationReportSchema(StrictSchema):
    run_id: str
    task_reconciliations: tuple[TaskReconciliationSchema, ...]
    fully_resolved: bool
    has_still_running: bool
    requires_manual_action: bool


@runtime_checkable
class ControlPlaneProvider(Protocol):
    """Stable control-plane boundary implemented without exposing runtime internals."""

    def inspect_capabilities(self) -> ProviderCapabilitiesSchema:
        """Describe provider operations and ownership boundaries."""

    def validate_workflow(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
    ) -> WorkflowValidationResultSchema:
        """Validate a portable workflow definition."""

    def inspect_workflow(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
    ) -> WorkflowInspectionSchema:
        """Return a deterministic static workflow inspection."""

    def execute_workflow(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
        *,
        parameters: dict[str, object] | None = None,
    ) -> ControlPlaneRunSchema:
        """Execute one workflow synchronously."""

    def inspect_run(self, run_id: str) -> ControlPlaneRunSchema:
        """Return one persisted run summary."""

    def list_runtime_events(self, run_id: str) -> tuple[RuntimeEventSchema, ...]:
        """Return redacted durable runtime events."""

    def retrieve_manifest(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
        run_id: str,
    ) -> dict[str, object]:
        """Return the canonical RunManifest schema-v1 representation."""

    def retrieve_lineage(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
        run_id: str,
    ) -> ExecutionLineageSchema:
        """Return deterministic execution lineage."""

    def request_cancellation(self, run_id: str, *, reason: str | None = None) -> None:
        """Request cancellation when the concrete provider supports it."""

    def assess_recovery(
        self,
        run_id: str,
        *,
        stale_after_seconds: float = 300.0,
    ) -> RecoveryAssessmentSchema:
        """Return read-only recovery classification."""

    def reconcile_run(
        self,
        run_id: str,
        *,
        stale_after_seconds: float = 300.0,
    ) -> ReconciliationReportSchema:
        """Return read-only external-work reconciliation."""

    def resume_run(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
        run_id: str,
        *,
        stale_after_seconds: float = 300.0,
    ) -> ControlPlaneRunSchema:
        """Resume one eligible persisted run."""


__all__ = [
    "CONTROL_PLANE_OPERATIONS",
    "CONTROL_PLANE_PROVIDER_CONTRACT_VERSION",
    "ControlPlaneOperation",
    "ControlPlaneProvider",
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
    "WorkflowValidationResultSchema",
]
