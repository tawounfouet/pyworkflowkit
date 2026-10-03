"""Canonical V2 durable execution-evidence values."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, StrEnum
from math import isfinite
from types import MappingProxyType
from typing import TypeAlias

from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]


class RuntimeEventType(StrEnum):
    """Canonical event classes derived from durable state evidence."""

    WORKFLOW_STATE_CHANGED = "WORKFLOW_STATE_CHANGED"
    TASK_STATE_CHANGED = "TASK_STATE_CHANGED"
    ATTEMPT_STATE_CHANGED = "ATTEMPT_STATE_CHANGED"


def normalize_json_value(value: object, *, path: str = "value") -> JsonValue:
    """Normalize strict finite portable JSON into immutable domain values."""

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{path} must contain only finite JSON numbers")
        return value
    if isinstance(value, Enum):
        return normalize_json_value(value.value, path=path)
    if isinstance(value, Mapping):
        normalized: dict[str, JsonValue] = {}
        for key in sorted(value, key=str):
            if not isinstance(key, str):
                raise TypeError(f"{path} mapping keys must be strings")
            normalized[key] = normalize_json_value(value[key], path=f"{path}.{key}")
        return MappingProxyType(normalized)
    if isinstance(value, (list, tuple)):
        return tuple(
            normalize_json_value(item, path=f"{path}[{index}]") for index, item in enumerate(value)
        )
    raise TypeError(f"{path} contains unsupported value type {type(value).__name__}")


def plain_json_value(value: JsonValue) -> object:
    """Convert immutable domain JSON values back to plain JSON containers."""

    if isinstance(value, Mapping):
        return {key: plain_json_value(nested) for key, nested in value.items()}
    if isinstance(value, tuple):
        return [plain_json_value(item) for item in value]
    return value


def canonical_json_digest(value: JsonValue) -> str:
    encoded = json.dumps(
        plain_json_value(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """Immutable V2 runtime event projected from durable transition evidence."""

    sequence: int
    event_type: RuntimeEventType
    workflow_run_id: WorkflowRunId
    occurred_at: datetime
    from_status: str | None
    to_status: str
    task_run_id: TaskRunId | None = None
    attempt_id: TaskAttemptId | None = None
    payload: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise TypeError("sequence must be an integer")
        if self.sequence < 1:
            raise ValueError("sequence must be greater than or equal to 1")
        if not isinstance(self.event_type, RuntimeEventType):
            raise TypeError("event_type must be a RuntimeEventType")
        if not isinstance(self.workflow_run_id, WorkflowRunId):
            raise TypeError("workflow_run_id must be a WorkflowRunId")
        if self.task_run_id is not None and not isinstance(self.task_run_id, TaskRunId):
            raise TypeError("task_run_id must be TaskRunId or None")
        if self.attempt_id is not None and not isinstance(self.attempt_id, TaskAttemptId):
            raise TypeError("attempt_id must be TaskAttemptId or None")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.from_status is not None and (
            not isinstance(self.from_status, str) or not self.from_status.strip()
        ):
            raise ValueError("from_status must be non-empty when provided")
        if not isinstance(self.to_status, str) or not self.to_status.strip():
            raise ValueError("to_status must not be empty")
        normalized = normalize_json_value(dict(self.payload), path="payload")
        if not isinstance(normalized, Mapping):
            raise TypeError("payload must normalize to a mapping")
        object.__setattr__(self, "payload", normalized)


@dataclass(frozen=True, slots=True)
class TaskOutputCheckpoint:
    """Durable JSON-portable output evidence for one successful TaskRun."""

    task_run_id: TaskRunId
    output: JsonValue
    recorded_at: datetime
    digest: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.task_run_id, TaskRunId):
            raise TypeError("task_run_id must be a TaskRunId")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        normalized = normalize_json_value(self.output, path="output")
        object.__setattr__(self, "output", normalized)
        expected = canonical_json_digest(normalized)
        if self.digest:
            if self.digest != expected:
                raise ValueError("digest does not match canonical output JSON")
        else:
            object.__setattr__(self, "digest", expected)


__all__ = [
    "JsonScalar",
    "JsonValue",
    "RuntimeEvent",
    "RuntimeEventType",
    "TaskOutputCheckpoint",
    "canonical_json_digest",
    "normalize_json_value",
    "plain_json_value",
]
