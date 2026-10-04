"""Explicit domain ↔ strict schema mappings for LOT-15 wire contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypeAlias

from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.diagnostics.model import Diagnostic, DiagnosticSeverity
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.identity import CorrelationId, WorkflowRunId
from pyworkflowkit.runtime.references import ExternalRunRef, WorkflowExecutionReference
from pyworkflowkit.serialization.schemas import (
    CorrelationContextSchema,
    DiagnosticSchema,
    ExternalRunRefSchema,
    FailureEvidenceSchema,
    StrictBoundarySchema,
    WorkflowExecutionReferenceSchema,
    parse_wire_datetime,
)

BoundaryValue: TypeAlias = (
    CorrelationContext | WorkflowExecutionReference | ExternalRunRef | FailureEvidence | Diagnostic
)


def schema_for_value(value: BoundaryValue) -> StrictBoundarySchema:
    """Map one supported domain boundary value to its strict schema."""

    if isinstance(value, CorrelationContext):
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
            traceparent=value.traceparent,
            tracestate=value.tracestate,
            baggage=dict(value.baggage) if value.baggage else None,
        )

    if isinstance(value, WorkflowExecutionReference):
        return WorkflowExecutionReferenceSchema(
            workflow_run_id=str(value.workflow_run_id),
            workflow_definition_id=value.workflow_definition_id,
            status=value.status,
            started_at=_format_wire_datetime(value.started_at),
            owner=value.owner,
            namespace=value.namespace,
            contract_version=value.contract_version,
        )
    if isinstance(value, ExternalRunRef):
        return _external_run_ref_schema(value)
    if isinstance(value, FailureEvidence):
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
                _external_run_ref_schema(value.external_run)
                if value.external_run is not None
                else None
            ),
            source_component=value.source_component,
            provider_code=value.provider_code,
            message_summary=value.message_summary,
            occurred_at=_format_required_wire_datetime(value.occurred_at),
            details=_pairs_to_dict(value.details, field_name="details"),
            contract_version=value.contract_version,
        )
    if isinstance(value, Diagnostic):
        return DiagnosticSchema(
            code=value.code,
            severity=value.severity.value,
            summary=value.summary,
            details=_pairs_to_dict(value.details, field_name="details"),
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
    raise TypeError(f"unsupported boundary value type {type(value).__name__}")


def value_from_schema(schema: StrictBoundarySchema) -> BoundaryValue:
    """Map one validated schema to its canonical V2 dataclass."""

    if isinstance(schema, CorrelationContextSchema):
        return CorrelationContext(
            correlation_id=CorrelationId.parse(schema.correlation_id),
            causation_id=schema.causation_id,
            parent_execution_id=schema.parent_execution_id,
            workflow_run_id=schema.workflow_run_id,
            task_run_id=schema.task_run_id,
            task_attempt_id=schema.task_attempt_id,
            ingestion_run_id=schema.ingestion_run_id,
            transformation_execution_id=schema.transformation_execution_id,
            trace_id=schema.trace_id,
            span_id=schema.span_id,
            traceparent=schema.traceparent,
            tracestate=schema.tracestate,
            baggage=dict(schema.baggage or {}),
        )

    if isinstance(schema, WorkflowExecutionReferenceSchema):
        return WorkflowExecutionReference(
            workflow_run_id=WorkflowRunId.parse(schema.workflow_run_id),
            workflow_definition_id=schema.workflow_definition_id,
            status=schema.status,
            started_at=(
                parse_wire_datetime(schema.started_at, field_name="started_at")
                if schema.started_at is not None
                else None
            ),
            owner=schema.owner,
            namespace=schema.namespace,
            contract_version=schema.contract_version,
        )
    if isinstance(schema, ExternalRunRefSchema):
        return _external_run_ref_value(schema)
    if isinstance(schema, FailureEvidenceSchema):
        return FailureEvidence(
            error_code=schema.error_code,
            category=FailureCategory(schema.category),
            retryability=Retryability(schema.retryability),
            uncertainty=OutcomeUncertainty(schema.uncertainty),
            correlation_id=CorrelationId.parse(schema.correlation_id),
            source_framework=schema.source_framework,
            workflow_run_id=schema.workflow_run_id,
            task_run_id=schema.task_run_id,
            task_attempt_id=schema.task_attempt_id,
            external_run=(
                _external_run_ref_value(schema.external_run)
                if schema.external_run is not None
                else None
            ),
            source_component=schema.source_component,
            provider_code=schema.provider_code,
            message_summary=schema.message_summary,
            occurred_at=parse_wire_datetime(schema.occurred_at, field_name="occurred_at"),
            details=tuple(sorted(schema.details.items())),
            contract_version=schema.contract_version,
        )
    if isinstance(schema, DiagnosticSchema):
        return Diagnostic(
            code=schema.code,
            severity=DiagnosticSeverity(schema.severity),
            summary=schema.summary,
            details=tuple(sorted(schema.details.items())),
            workflow_run_id=schema.workflow_run_id,
            task_run_id=schema.task_run_id,
            task_attempt_id=schema.task_attempt_id,
            correlation_id=(
                CorrelationId.parse(schema.correlation_id)
                if schema.correlation_id is not None
                else None
            ),
            source_component=schema.source_component,
            decision_context=schema.decision_context,
            related_policy=schema.related_policy,
            source_framework=schema.source_framework,
        )
    raise TypeError(f"unsupported boundary schema type {type(schema).__name__}")


def _external_run_ref_schema(value: ExternalRunRef) -> ExternalRunRefSchema:
    return ExternalRunRefSchema(
        provider=value.provider,
        external_run_id=value.external_run_id,
        kind=value.kind,
        status_hint=value.status_hint,
        status_locator=value.status_locator,
        correlation_id=(str(value.correlation_id) if value.correlation_id is not None else None),
        causation_id=value.causation_id,
        metadata=_pairs_to_dict(value.metadata, field_name="metadata"),
        namespace=value.namespace,
        contract_version=value.contract_version,
    )


def _external_run_ref_value(schema: ExternalRunRefSchema) -> ExternalRunRef:
    return ExternalRunRef(
        provider=schema.provider,
        external_run_id=schema.external_run_id,
        kind=schema.kind,
        status_hint=schema.status_hint,
        status_locator=schema.status_locator,
        correlation_id=(
            CorrelationId.parse(schema.correlation_id)
            if schema.correlation_id is not None
            else None
        ),
        causation_id=schema.causation_id,
        metadata=tuple(sorted(schema.metadata.items())),
        namespace=schema.namespace,
        contract_version=schema.contract_version,
    )


def _pairs_to_dict(
    values: tuple[tuple[str, str], ...],
    *,
    field_name: str,
) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in values:
        if key in result:
            raise ValueError(f"{field_name} contains duplicate key {key!r}")
        result[key] = value
    return result


def _format_wire_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _format_required_wire_datetime(value)


def _format_required_wire_datetime(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("wire datetime must be timezone-aware")
    normalized = value.astimezone(UTC)
    rendered = normalized.isoformat(timespec="microseconds")
    if rendered.endswith("+00:00"):
        rendered = rendered[:-6] + "Z"
    return rendered


__all__ = [
    "BoundaryValue",
    "schema_for_value",
    "value_from_schema",
]
