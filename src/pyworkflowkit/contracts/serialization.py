"""Strict portable serialization schemas and canonical JSON codec."""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import Enum
from math import isfinite
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, field_validator

from pyworkflowkit.domain.enums import (
    BackoffStrategy,
    FailurePolicy,
    RuntimeEventType,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.errors import SerializationError


def _normalize_datetime(value: datetime | None, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
    return value.astimezone(UTC)


def _portable_json_value(value: object, *, path: str) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise SerializationError(
                path=path,
                value_type=type(value).__name__,
                reason="non-finite floating-point values are not portable JSON",
            )
        return value
    if isinstance(value, Enum):
        return _portable_json_value(value.value, path=path)
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, nested in sorted(value.items(), key=lambda item: str(item[0])):
            if not isinstance(key, str):
                raise SerializationError(
                    path=path,
                    value_type=f"mapping-key:{type(key).__name__}",
                    reason="portable JSON object keys must be strings",
                )
            normalized[key] = _portable_json_value(nested, path=f"{path}.{key}")
        return normalized
    if isinstance(value, (list, tuple)):
        return [
            _portable_json_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise SerializationError(
        path=path,
        value_type=type(value).__name__,
        reason="value is not representable as portable JSON",
    )


def _portable_json_mapping(values: Mapping[str, object], *, path: str) -> dict[str, object]:
    normalized = _portable_json_value(values, path=path)
    if not isinstance(normalized, dict):
        raise TypeError("portable JSON mapping normalization must return a dict")
    return normalized


class StrictSchema(BaseModel):
    """Base schema with immutable, extra-forbidden boundary semantics."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_assignment=True,
    )


class RetryPolicySchema(StrictSchema):
    max_attempts: int = 1
    backoff_strategy: BackoffStrategy = BackoffStrategy.NONE
    delay_seconds: float = 0.0
    max_delay_seconds: float | None = None
    retryable_error_categories: tuple[str, ...] = ()


class WorkflowParameterSchema(StrictSchema):
    name: str
    required: bool = True
    default: object | None = None
    sensitive: bool = False

    @field_validator("default")
    @classmethod
    def validate_default(cls, value: object) -> object:
        return _portable_json_value(value, path="workflow_parameter.default")


class TaskDefinitionSchema(StrictSchema):
    task_id: str
    handler_ref: str | None = None
    depends_on: tuple[str, ...] = ()
    retry_policy: RetryPolicySchema = RetryPolicySchema()
    executor_key: str = "local"
    timeout_seconds: float | None = None
    tags: tuple[str, ...] = ()
    description: str | None = None


class WorkflowDefinitionSchema(StrictSchema):
    workflow_id: str
    version: str
    tasks: tuple[TaskDefinitionSchema, ...]
    parameters: tuple[WorkflowParameterSchema, ...] = ()
    failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST
    description: str | None = None


class WorkflowRunSchema(StrictSchema):
    run_id: str
    workflow_id: str
    workflow_version: str
    status: WorkflowRunStatus
    parameters: dict[str, object]
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: dict[str, object]) -> dict[str, object]:
        return _portable_json_mapping(value, path="workflow_run.parameters")

    @field_validator("created_at", "started_at", "finished_at")
    @classmethod
    def normalize_datetimes(
        cls,
        value: datetime | None,
        info: object,
    ) -> datetime | None:
        field_name = getattr(info, "field_name", "datetime")
        return _normalize_datetime(value, field_name=str(field_name))


class TaskRunSchema(StrictSchema):
    task_run_id: str
    run_id: str
    task_id: str
    status: TaskRunStatus
    skip_reason: SkipReason | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_validator("created_at", "started_at", "finished_at")
    @classmethod
    def normalize_datetimes(
        cls,
        value: datetime | None,
        info: object,
    ) -> datetime | None:
        field_name = getattr(info, "field_name", "datetime")
        return _normalize_datetime(value, field_name=str(field_name))


class TaskAttemptSchema(StrictSchema):
    attempt_id: str
    task_run_id: str
    attempt_number: int
    status: TaskAttemptStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_type: str | None = None
    error_message: str | None = None
    error_category: str | None = None
    error_metadata: dict[str, object]

    @field_validator("error_metadata")
    @classmethod
    def validate_error_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        return _portable_json_mapping(value, path="task_attempt.error_metadata")

    @field_validator("started_at", "finished_at")
    @classmethod
    def normalize_datetimes(
        cls,
        value: datetime | None,
        info: object,
    ) -> datetime | None:
        field_name = getattr(info, "field_name", "datetime")
        return _normalize_datetime(value, field_name=str(field_name))


class RuntimeEventSchema(StrictSchema):
    event_id: str
    event_type: RuntimeEventType
    run_id: str
    occurred_at: datetime
    event_sequence: int | None = None
    task_run_id: str | None = None
    task_id: str | None = None
    attempt_number: int | None = None
    payload: dict[str, object]

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, value: dict[str, object]) -> dict[str, object]:
        return _portable_json_mapping(value, path="runtime_event.payload")

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at(cls, value: datetime) -> datetime:
        normalized = _normalize_datetime(value, field_name="occurred_at")
        if normalized is None:
            raise TypeError("occurred_at cannot be None")
        return normalized


class ArtifactReferenceSchema(StrictSchema):
    artifact_id: str
    name: str
    uri: str
    media_type: str | None = None
    checksum: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, object]

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        return _portable_json_mapping(value, path="artifact.metadata")


class ExternalRunRefSchema(StrictSchema):
    external_ref_id: str
    provider: str
    external_run_id: str
    uri: str | None = None
    metadata: dict[str, object]

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, object]) -> dict[str, object]:
        return _portable_json_mapping(value, path="external_run_ref.metadata")


SchemaT = TypeVar("SchemaT", bound=StrictSchema)


class SchemaCodec:
    """Canonical JSON encoding/decoding for strict schemas."""

    @staticmethod
    def to_dict(schema: StrictSchema) -> dict[str, object]:
        return schema.model_dump(mode="json")

    @staticmethod
    def to_json(schema: StrictSchema) -> str:
        return json.dumps(
            SchemaCodec.to_dict(schema),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def from_json(schema_type: type[SchemaT], payload: str) -> SchemaT:
        return schema_type.model_validate_json(payload)


__all__ = [
    "ArtifactReferenceSchema",
    "ExternalRunRefSchema",
    "RetryPolicySchema",
    "RuntimeEventSchema",
    "SchemaCodec",
    "StrictSchema",
    "TaskAttemptSchema",
    "TaskDefinitionSchema",
    "TaskRunSchema",
    "WorkflowDefinitionSchema",
    "WorkflowParameterSchema",
    "WorkflowRunSchema",
]
