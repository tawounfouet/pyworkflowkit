"""Strict Pydantic boundary schemas for canonical V2 wire contracts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from math import isfinite
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.diagnostics.model import DiagnosticSeverity
from pyworkflowkit.runtime.evidence import RuntimeEventType
from pyworkflowkit.states import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus


def canonical_timestamp(value: datetime | str | None, *, field_name: str) -> str | None:
    """Normalize one timezone-aware timestamp to canonical UTC ISO-8601 with Z."""

    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{field_name} must not be blank")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO-8601 timestamp") from exc
        value = parsed
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime or ISO-8601 string")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def portable_json_value(value: object, *, path: str) -> object:
    """Return detached strict JSON data without implicit string fallback."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{path} contains a non-finite JSON number")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key in sorted(value, key=str):
            if not isinstance(key, str):
                raise TypeError(f"{path} mapping keys must be strings")
            normalized[key] = portable_json_value(value[key], path=f"{path}.{key}")
        return normalized
    if isinstance(value, (list, tuple)):
        return [
            portable_json_value(item, path=f"{path}[{index}]") for index, item in enumerate(value)
        ]
    raise TypeError(f"{path} contains unsupported value type {type(value).__name__}")


class StrictSchema(BaseModel):
    """Immutable extra-forbidden V2 wire-schema baseline."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )


class WireEnvelope(StrictSchema):
    """Versioned non-executable wire envelope."""

    contract: str
    contract_version: str
    payload: dict[str, Any]

    @field_validator("contract", "contract_version")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("wire envelope text fields must not be blank")
        return value

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        normalized = portable_json_value(value, path="payload")
        if not isinstance(normalized, dict):
            raise TypeError("wire envelope payload must normalize to a dict")
        return normalized


class CorrelationContextSchema(StrictSchema):
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


class WorkflowExecutionReferenceSchema(StrictSchema):
    workflow_run_id: str
    workflow_definition_id: str
    status: str | None = None
    started_at: str | None = None
    owner: str
    namespace: str
    contract_version: str

    @field_validator("started_at")
    @classmethod
    def validate_started_at(cls, value: str | None) -> str | None:
        return canonical_timestamp(value, field_name="started_at")


class ExternalRunRefSchema(StrictSchema):
    provider: str
    external_run_id: str
    kind: str
    status_hint: str | None = None
    status_locator: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
    namespace: str
    contract_version: str


class FailureEvidenceSchema(StrictSchema):
    error_code: str
    category: str
    retryability: str
    uncertainty: str
    correlation_id: str
    source_framework: str
    workflow_run_id: str | None = None
    task_run_id: str | None = None
    task_attempt_id: str | None = None
    external_run: ExternalRunRefSchema | None = None
    source_component: str | None = None
    provider_code: str | None = None
    message_summary: str | None = None
    occurred_at: str
    details: tuple[tuple[str, str], ...] = ()
    contract_version: str

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        FailureCategory(value)
        return value

    @field_validator("retryability")
    @classmethod
    def validate_retryability(cls, value: str) -> str:
        Retryability(value)
        return value

    @field_validator("uncertainty")
    @classmethod
    def validate_uncertainty(cls, value: str) -> str:
        OutcomeUncertainty(value)
        return value

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: str) -> str:
        normalized = canonical_timestamp(value, field_name="occurred_at")
        if normalized is None:
            raise TypeError("occurred_at cannot be None")
        return normalized


class DiagnosticSchema(StrictSchema):
    code: str
    severity: str
    summary: str
    details: tuple[tuple[str, str], ...] = ()
    workflow_run_id: str | None = None
    task_run_id: str | None = None
    task_attempt_id: str | None = None
    correlation_id: str | None = None
    source_component: str | None = None
    decision_context: str | None = None
    related_policy: str | None = None
    source_framework: str

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: str) -> str:
        DiagnosticSeverity(value)
        return value


class RuntimeEventSchema(StrictSchema):
    sequence: int
    event_id: str
    event_type: str
    workflow_run_id: str
    occurred_at: str
    from_status: str | None
    to_status: str
    task_run_id: str | None = None
    attempt_id: str | None = None
    task_key: str | None = None
    attempt_number: int | None = None
    payload: dict[str, Any]

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        RuntimeEventType(value)
        return value

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: str) -> str:
        normalized = canonical_timestamp(value, field_name="occurred_at")
        if normalized is None:
            raise TypeError("occurred_at cannot be None")
        return normalized

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        normalized = portable_json_value(value, path="runtime_event.payload")
        if not isinstance(normalized, dict):
            raise TypeError("runtime event payload must normalize to a dict")
        return normalized


class TaskOutputCheckpointSchema(StrictSchema):
    task_run_id: str
    output: Any
    recorded_at: str
    digest: str

    @field_validator("output")
    @classmethod
    def validate_output(cls, value: Any) -> object:
        return portable_json_value(value, path="task_output.output")

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: str) -> str:
        normalized = canonical_timestamp(value, field_name="recorded_at")
        if normalized is None:
            raise TypeError("recorded_at cannot be None")
        return normalized


class ManifestAttemptSchema(StrictSchema):
    attempt_id: str
    attempt_number: int
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        TaskAttemptStatus(value)
        return value


class ManifestTaskRunSchema(StrictSchema):
    task_run_id: str
    task_key: str
    status: str
    attempts: tuple[ManifestAttemptSchema, ...]
    external_runs: tuple[ExternalRunRefSchema, ...]
    output: Any | None = None
    output_digest: str | None = None
    output_recorded_at: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        TaskRunStatus(value)
        return value

    @field_validator("output")
    @classmethod
    def validate_output(cls, value: Any | None) -> object | None:
        return portable_json_value(value, path="manifest_task.output")

    @field_validator("output_recorded_at")
    @classmethod
    def validate_output_recorded_at(cls, value: str | None) -> str | None:
        return canonical_timestamp(value, field_name="output_recorded_at")


class RunManifestSchema(StrictSchema):
    schema_version: str
    workflow_run_id: str
    workflow_name: str
    workflow_version: str
    definition_fingerprint: str
    plan_fingerprint: str
    status: str
    created_at: str
    started_at: str | None
    ended_at: str | None
    tasks: tuple[ManifestTaskRunSchema, ...]

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        WorkflowRunStatus(value)
        return value

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: str) -> str:
        normalized = canonical_timestamp(value, field_name="created_at")
        if normalized is None:
            raise TypeError("created_at cannot be None")
        return normalized

    @field_validator("started_at", "ended_at")
    @classmethod
    def validate_optional_timestamps(cls, value: str | None) -> str | None:
        return canonical_timestamp(value, field_name="manifest_timestamp")


__all__ = [
    "CorrelationContextSchema",
    "DiagnosticSchema",
    "ExternalRunRefSchema",
    "FailureEvidenceSchema",
    "ManifestAttemptSchema",
    "ManifestTaskRunSchema",
    "RunManifestSchema",
    "RuntimeEventSchema",
    "StrictSchema",
    "TaskOutputCheckpointSchema",
    "WireEnvelope",
    "WorkflowExecutionReferenceSchema",
    "canonical_timestamp",
    "portable_json_value",
]
