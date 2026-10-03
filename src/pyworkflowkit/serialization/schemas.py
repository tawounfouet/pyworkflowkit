"""Strict non-executable schemas for V2 boundary wire contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.diagnostics.model import DiagnosticSeverity

_FAILURE_CATEGORIES = frozenset(item.value for item in FailureCategory)
_RETRYABILITY_VALUES = frozenset(item.value for item in Retryability)
_UNCERTAINTY_VALUES = frozenset(item.value for item in OutcomeUncertainty)
_DIAGNOSTIC_SEVERITIES = frozenset(item.value for item in DiagnosticSeverity)


class StrictBoundarySchema(BaseModel):
    """Immutable extra-forbidden schema used only for data validation."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )


class WireEnvelopeSchema(StrictBoundarySchema):
    """Versioned non-executable envelope for one known boundary contract."""

    contract: str
    contract_version: str
    payload: dict[str, object]

    @field_validator("contract", "contract_version")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("wire envelope text fields must not be blank")
        return value


class CorrelationContextSchema(StrictBoundarySchema):
    correlation_id: str
    causation_id: str | None = None
    parent_execution_id: str | None = None
    workflow_run_id: str | None = None
    task_run_id: str | None = None
    task_attempt_id: str | None = None
    ingestion_run_id: str | None = None
    transformation_execution_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None

    @field_validator(
        "correlation_id",
        "causation_id",
        "parent_execution_id",
        "workflow_run_id",
        "task_run_id",
        "task_attempt_id",
        "ingestion_run_id",
        "transformation_execution_id",
        "trace_id",
        "span_id",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("correlation context text fields must not be blank")
        return value


class WorkflowExecutionReferenceSchema(StrictBoundarySchema):
    workflow_run_id: str
    workflow_definition_id: str
    status: str | None = None
    started_at: str | None = None
    owner: str = "pyworkflowkit"
    namespace: str = "pyworkflowkit.workflow_execution"
    contract_version: str = "1"

    @field_validator(
        "workflow_run_id",
        "workflow_definition_id",
        "status",
        "owner",
        "namespace",
        "contract_version",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("workflow execution reference text fields must not be blank")
        return value

    @field_validator("started_at")
    @classmethod
    def validate_started_at(cls, value: str | None) -> str | None:
        if value is not None:
            _parse_wire_datetime(value, field_name="started_at")
        return value


class ExternalRunRefSchema(StrictBoundarySchema):
    provider: str
    external_run_id: str
    kind: str
    status_hint: str | None = None
    status_locator: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    namespace: str = "pyworkflowkit.external_run"
    contract_version: str = "1"

    @field_validator(
        "provider",
        "external_run_id",
        "kind",
        "status_hint",
        "status_locator",
        "correlation_id",
        "causation_id",
        "namespace",
        "contract_version",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("external run reference text fields must not be blank")
        return value


class FailureEvidenceSchema(StrictBoundarySchema):
    error_code: str
    category: str
    retryability: str
    uncertainty: str
    correlation_id: str
    source_framework: str = "pyworkflowkit"
    workflow_run_id: str | None = None
    task_run_id: str | None = None
    task_attempt_id: str | None = None
    external_run: ExternalRunRefSchema | None = None
    source_component: str | None = None
    provider_code: str | None = None
    message_summary: str | None = None
    occurred_at: str
    details: dict[str, str] = Field(default_factory=dict)
    contract_version: str = "1"

    @field_validator(
        "error_code",
        "correlation_id",
        "source_framework",
        "workflow_run_id",
        "task_run_id",
        "task_attempt_id",
        "source_component",
        "provider_code",
        "message_summary",
        "contract_version",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("failure evidence text fields must not be blank")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        return _validate_enum_value(value, _FAILURE_CATEGORIES, field_name="category")

    @field_validator("retryability")
    @classmethod
    def validate_retryability(cls, value: str) -> str:
        return _validate_enum_value(value, _RETRYABILITY_VALUES, field_name="retryability")

    @field_validator("uncertainty")
    @classmethod
    def validate_uncertainty(cls, value: str) -> str:
        return _validate_enum_value(value, _UNCERTAINTY_VALUES, field_name="uncertainty")

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: str) -> str:
        _parse_wire_datetime(value, field_name="occurred_at")
        return value


class DiagnosticSchema(StrictBoundarySchema):
    code: str
    severity: str
    summary: str
    details: dict[str, str] = Field(default_factory=dict)
    workflow_run_id: str | None = None
    task_run_id: str | None = None
    task_attempt_id: str | None = None
    correlation_id: str | None = None
    source_component: str | None = None
    decision_context: str | None = None
    related_policy: str | None = None
    source_framework: str = "pyworkflowkit"

    @field_validator(
        "code",
        "summary",
        "workflow_run_id",
        "task_run_id",
        "task_attempt_id",
        "correlation_id",
        "source_component",
        "decision_context",
        "related_policy",
        "source_framework",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("diagnostic text fields must not be blank")
        return value

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: str) -> str:
        return _validate_enum_value(value, _DIAGNOSTIC_SEVERITIES, field_name="severity")


def parse_wire_datetime(value: str, *, field_name: str) -> datetime:
    """Parse one timezone-aware ISO-8601 wire timestamp."""

    return _parse_wire_datetime(value, field_name=field_name)


def _parse_wire_datetime(value: str, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty ISO-8601 string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be valid ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return parsed


def _validate_enum_value(
    value: str,
    allowed: frozenset[str],
    *,
    field_name: str,
) -> str:
    if value not in allowed:
        raise ValueError(f"{field_name} must be one of {sorted(allowed)!r}")
    return value


__all__ = [
    "CorrelationContextSchema",
    "DiagnosticSchema",
    "ExternalRunRefSchema",
    "FailureEvidenceSchema",
    "StrictBoundarySchema",
    "WireEnvelopeSchema",
    "WorkflowExecutionReferenceSchema",
    "parse_wire_datetime",
]
