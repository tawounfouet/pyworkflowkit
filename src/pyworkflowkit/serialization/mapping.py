"""Explicit domain ↔ strict-schema mapping for V2 portable contracts."""

from __future__ import annotations

from datetime import datetime

from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.diagnostics.model import Diagnostic, DiagnosticSeverity
from pyworkflowkit.lineage.model import (
    ManifestAttempt,
    ManifestTaskRun,
    RunManifest,
)
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.evidence import (
    RuntimeEvent,
    RuntimeEventType,
    TaskOutputCheckpoint,
    normalize_json_value,
    plain_json_value,
)
from pyworkflowkit.runtime.identity import (
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.runtime.references import ExternalRunRef, WorkflowExecutionReference
from pyworkflowkit.serialization.schemas import (
    CorrelationContextSchema,
    DiagnosticSchema,
    ExternalRunRefSchema,
    FailureEvidenceSchema,
    ManifestAttemptSchema,
    ManifestTaskRunSchema,
    RunManifestSchema,
    RuntimeEventSchema,
    TaskOutputCheckpointSchema,
    WorkflowExecutionReferenceSchema,
    canonical_timestamp,
)
from pyworkflowkit.states import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def correlation_context_to_schema(value: CorrelationContext) -> CorrelationContextSchema:
    return CorrelationContextSchema(
        correlation_id=str(value.correlation_id),
        causation_id=value.causation_id,
        parent_execution_id=value.parent_execution_id,
        workflow_run_id=value.workflow_run_id,
        task_run_id=value.task_run_id,
        task_attempt_id=value.task_attempt_id,
        ingestion_run_id=value.ingestion_run_id,
        transformation_execution_id=value.transformation_execution_id,
        trace_id=value.trace_id,
        span_id=value.span_id,
    )


def correlation_context_from_schema(value: CorrelationContextSchema) -> CorrelationContext:
    return CorrelationContext(
        correlation_id=CorrelationId.parse(value.correlation_id),
        causation_id=value.causation_id,
        parent_execution_id=value.parent_execution_id,
        workflow_run_id=value.workflow_run_id,
        task_run_id=value.task_run_id,
        task_attempt_id=value.task_attempt_id,
        ingestion_run_id=value.ingestion_run_id,
        transformation_execution_id=value.transformation_execution_id,
        trace_id=value.trace_id,
        span_id=value.span_id,
    )


def workflow_execution_reference_to_schema(
    value: WorkflowExecutionReference,
) -> WorkflowExecutionReferenceSchema:
    return WorkflowExecutionReferenceSchema(
        workflow_run_id=str(value.workflow_run_id),
        workflow_definition_id=value.workflow_definition_id,
        status=value.status,
        started_at=canonical_timestamp(value.started_at, field_name="started_at"),
        owner=value.owner,
        namespace=value.namespace,
        contract_version=value.contract_version,
    )


def workflow_execution_reference_from_schema(
    value: WorkflowExecutionReferenceSchema,
) -> WorkflowExecutionReference:
    return WorkflowExecutionReference(
        workflow_run_id=WorkflowRunId.parse(value.workflow_run_id),
        workflow_definition_id=value.workflow_definition_id,
        status=value.status,
        started_at=_parse_timestamp(value.started_at) if value.started_at is not None else None,
        owner=value.owner,
        namespace=value.namespace,
        contract_version=value.contract_version,
    )


def external_run_ref_to_schema(value: ExternalRunRef) -> ExternalRunRefSchema:
    return ExternalRunRefSchema(
        provider=value.provider,
        external_run_id=value.external_run_id,
        kind=value.kind,
        status_hint=value.status_hint,
        status_locator=value.status_locator,
        correlation_id=(
            str(value.correlation_id) if value.correlation_id is not None else None
        ),
        causation_id=value.causation_id,
        metadata=value.metadata,
        namespace=value.namespace,
        contract_version=value.contract_version,
    )


def external_run_ref_from_schema(value: ExternalRunRefSchema) -> ExternalRunRef:
    return ExternalRunRef(
        provider=value.provider,
        external_run_id=value.external_run_id,
        kind=value.kind,
        status_hint=value.status_hint,
        status_locator=value.status_locator,
        correlation_id=(
            CorrelationId.parse(value.correlation_id)
            if value.correlation_id is not None
            else None
        ),
        causation_id=value.causation_id,
        metadata=value.metadata,
        namespace=value.namespace,
        contract_version=value.contract_version,
    )


def failure_evidence_to_schema(value: FailureEvidence) -> FailureEvidenceSchema:
    return FailureEvidenceSchema(
        error_code=value.error_code,
        category=value.category.value,
        retryability=value.retryability.value,
        uncertainty=value.uncertainty.value,
        correlation_id=str(value.correlation_id),
        source_framework=value.source_framework,
        workflow_run_id=value.workflow_run_id,
        task_run_id=value.task_run_id,
        task_attempt_id=value.task_attempt_id,
        external_run=(
            external_run_ref_to_schema(value.external_run)
            if value.external_run is not None
            else None
        ),
        source_component=value.source_component,
        provider_code=value.provider_code,
        message_summary=value.message_summary,
        occurred_at=canonical_timestamp(value.occurred_at, field_name="occurred_at"),
        details=value.details,
        contract_version=value.contract_version,
    )


def failure_evidence_from_schema(value: FailureEvidenceSchema) -> FailureEvidence:
    return FailureEvidence(
        error_code=value.error_code,
        category=FailureCategory(value.category),
        retryability=Retryability(value.retryability),
        uncertainty=OutcomeUncertainty(value.uncertainty),
        correlation_id=CorrelationId.parse(value.correlation_id),
        source_framework=value.source_framework,
        workflow_run_id=value.workflow_run_id,
        task_run_id=value.task_run_id,
        task_attempt_id=value.task_attempt_id,
        external_run=(
            external_run_ref_from_schema(value.external_run)
            if value.external_run is not None
            else None
        ),
        source_component=value.source_component,
        provider_code=value.provider_code,
        message_summary=value.message_summary,
        occurred_at=_parse_timestamp(value.occurred_at),
        details=value.details,
        contract_version=value.contract_version,
    )


def diagnostic_to_schema(value: Diagnostic) -> DiagnosticSchema:
    return DiagnosticSchema(
        code=value.code,
        severity=value.severity.value,
        summary=value.summary,
        details=value.details,
        workflow_run_id=value.workflow_run_id,
        task_run_id=value.task_run_id,
        task_attempt_id=value.task_attempt_id,
        correlation_id=(
            str(value.correlation_id) if value.correlation_id is not None else None
        ),
        source_component=value.source_component,
        decision_context=value.decision_context,
        related_policy=value.related_policy,
        source_framework=value.source_framework,
    )


def diagnostic_from_schema(value: DiagnosticSchema) -> Diagnostic:
    return Diagnostic(
        code=value.code,
        severity=DiagnosticSeverity(value.severity),
        summary=value.summary,
        details=value.details,
        workflow_run_id=value.workflow_run_id,
        task_run_id=value.task_run_id,
        task_attempt_id=value.task_attempt_id,
        correlation_id=(
            CorrelationId.parse(value.correlation_id)
            if value.correlation_id is not None
            else None
        ),
        source_component=value.source_component,
        decision_context=value.decision_context,
        related_policy=value.related_policy,
        source_framework=value.source_framework,
    )


def runtime_event_to_schema(value: RuntimeEvent) -> RuntimeEventSchema:
    payload = plain_json_value(value.payload)
    if not isinstance(payload, dict):
        raise TypeError("RuntimeEvent payload must serialize to a dict")
    return RuntimeEventSchema(
        sequence=value.sequence,
        event_id=value.event_id,
        event_type=value.event_type.value,
        workflow_run_id=str(value.workflow_run_id),
        occurred_at=canonical_timestamp(value.occurred_at, field_name="occurred_at"),
        from_status=value.from_status,
        to_status=value.to_status,
        task_run_id=str(value.task_run_id) if value.task_run_id is not None else None,
        attempt_id=str(value.attempt_id) if value.attempt_id is not None else None,
        task_key=value.task_key,
        attempt_number=value.attempt_number,
        payload=payload,
    )


def runtime_event_from_schema(value: RuntimeEventSchema) -> RuntimeEvent:
    return RuntimeEvent(
        sequence=value.sequence,
        event_id=value.event_id,
        event_type=RuntimeEventType(value.event_type),
        workflow_run_id=WorkflowRunId.parse(value.workflow_run_id),
        occurred_at=_parse_timestamp(value.occurred_at),
        from_status=value.from_status,
        to_status=value.to_status,
        task_run_id=(
            TaskRunId.parse(value.task_run_id) if value.task_run_id is not None else None
        ),
        attempt_id=(
            TaskAttemptId.parse(value.attempt_id) if value.attempt_id is not None else None
        ),
        task_key=value.task_key,
        attempt_number=value.attempt_number,
        payload=value.payload,
    )


def task_output_checkpoint_to_schema(
    value: TaskOutputCheckpoint,
) -> TaskOutputCheckpointSchema:
    return TaskOutputCheckpointSchema(
        task_run_id=str(value.task_run_id),
        output=plain_json_value(value.output),
        recorded_at=canonical_timestamp(value.recorded_at, field_name="recorded_at"),
        digest=value.digest,
    )


def task_output_checkpoint_from_schema(
    value: TaskOutputCheckpointSchema,
) -> TaskOutputCheckpoint:
    return TaskOutputCheckpoint(
        task_run_id=TaskRunId.parse(value.task_run_id),
        output=normalize_json_value(value.output, path="output"),
        recorded_at=_parse_timestamp(value.recorded_at),
        digest=value.digest,
    )


def manifest_attempt_to_schema(value: ManifestAttempt) -> ManifestAttemptSchema:
    return ManifestAttemptSchema(
        attempt_id=str(value.attempt_id),
        attempt_number=value.attempt_number,
        status=value.status.value,
    )


def manifest_attempt_from_schema(value: ManifestAttemptSchema) -> ManifestAttempt:
    return ManifestAttempt(
        attempt_id=TaskAttemptId.parse(value.attempt_id),
        attempt_number=value.attempt_number,
        status=TaskAttemptStatus(value.status),
    )


def manifest_task_run_to_schema(value: ManifestTaskRun) -> ManifestTaskRunSchema:
    return ManifestTaskRunSchema(
        task_run_id=str(value.task_run_id),
        task_key=value.task_key,
        status=value.status.value,
        attempts=tuple(manifest_attempt_to_schema(item) for item in value.attempts),
        external_runs=tuple(
            external_run_ref_to_schema(item) for item in value.external_runs
        ),
        output=(
            plain_json_value(value.output) if value.output is not None else None
        ),
        output_digest=value.output_digest,
        output_recorded_at=value.output_recorded_at,
    )


def manifest_task_run_from_schema(value: ManifestTaskRunSchema) -> ManifestTaskRun:
    return ManifestTaskRun(
        task_run_id=TaskRunId.parse(value.task_run_id),
        task_key=value.task_key,
        status=TaskRunStatus(value.status),
        attempts=tuple(manifest_attempt_from_schema(item) for item in value.attempts),
        external_runs=tuple(
            external_run_ref_from_schema(item) for item in value.external_runs
        ),
        output=(
            normalize_json_value(value.output, path="manifest_task.output")
            if value.output is not None
            else None
        ),
        output_digest=value.output_digest,
        output_recorded_at=value.output_recorded_at,
    )


def run_manifest_to_schema(value: RunManifest) -> RunManifestSchema:
    return RunManifestSchema(
        schema_version=value.schema_version,
        workflow_run_id=str(value.workflow_run_id),
        workflow_name=value.workflow_name,
        workflow_version=value.workflow_version,
        definition_fingerprint=value.definition_fingerprint,
        plan_fingerprint=value.plan_fingerprint,
        status=value.status.value,
        created_at=value.created_at,
        started_at=value.started_at,
        ended_at=value.ended_at,
        tasks=tuple(manifest_task_run_to_schema(item) for item in value.tasks),
    )


def run_manifest_from_schema(value: RunManifestSchema) -> RunManifest:
    return RunManifest(
        schema_version=value.schema_version,
        workflow_run_id=WorkflowRunId.parse(value.workflow_run_id),
        workflow_name=value.workflow_name,
        workflow_version=value.workflow_version,
        definition_fingerprint=value.definition_fingerprint,
        plan_fingerprint=value.plan_fingerprint,
        status=WorkflowRunStatus(value.status),
        created_at=value.created_at,
        started_at=value.started_at,
        ended_at=value.ended_at,
        tasks=tuple(manifest_task_run_from_schema(item) for item in value.tasks),
    )


__all__ = [
    "correlation_context_from_schema",
    "correlation_context_to_schema",
    "diagnostic_from_schema",
    "diagnostic_to_schema",
    "external_run_ref_from_schema",
    "external_run_ref_to_schema",
    "failure_evidence_from_schema",
    "failure_evidence_to_schema",
    "manifest_attempt_from_schema",
    "manifest_attempt_to_schema",
    "manifest_task_run_from_schema",
    "manifest_task_run_to_schema",
    "run_manifest_from_schema",
    "run_manifest_to_schema",
    "runtime_event_from_schema",
    "runtime_event_to_schema",
    "task_output_checkpoint_from_schema",
    "task_output_checkpoint_to_schema",
    "workflow_execution_reference_from_schema",
    "workflow_execution_reference_to_schema",
]
