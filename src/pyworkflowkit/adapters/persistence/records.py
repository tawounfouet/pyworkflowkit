"""Neutral persistence row DTOs.

These are not ORM entities. SQLAlchemy models introduced later map to/from
these records rather than becoming the domain model.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class WorkflowRunRow:
    run_id: str
    workflow_id: str
    workflow_version: str
    status: str
    parameters: Mapping[str, object]
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class TaskRunRow:
    task_run_id: str
    run_id: str
    task_id: str
    status: str
    skip_reason: str | None
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class TaskAttemptRow:
    attempt_id: str
    task_run_id: str
    attempt_number: int
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_type: str | None
    error_message: str | None
    error_category: str | None
    error_metadata: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class RuntimeEventRow:
    event_id: str
    event_type: str
    run_id: str
    occurred_at: datetime
    event_sequence: int | None
    task_run_id: str | None
    task_id: str | None
    attempt_number: int | None
    payload: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ArtifactReferenceRow:
    artifact_id: str
    task_run_id: str
    name: str
    uri: str
    media_type: str | None
    checksum: str | None
    size_bytes: int | None
    metadata: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ExternalRunRefRow:
    external_ref_id: str
    task_run_id: str
    provider: str
    external_run_id: str
    uri: str | None
    metadata: Mapping[str, object]


__all__ = [
    "ArtifactReferenceRow",
    "ExternalRunRefRow",
    "RuntimeEventRow",
    "TaskAttemptRow",
    "TaskRunRow",
    "WorkflowRunRow",
]
