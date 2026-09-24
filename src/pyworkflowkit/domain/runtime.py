"""Mutable runtime entities and immutable runtime events."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from pyworkflowkit.domain.enums import (
    TASK_TERMINAL_STATUSES,
    WORKFLOW_TERMINAL_STATUSES,
    RuntimeEventType,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import (
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
    validate_non_empty_identifier,
)


def _freeze_mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(values))


def _ensure_aware_datetime(
    value: datetime | None,
    *,
    field_name: str,
) -> None:
    if value is None:
        return
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def _validate_positive_integer(
    value: int,
    *,
    field_name: str,
) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 1:
        raise ValueError(f"{field_name} must be greater than or equal to 1.")


@dataclass(slots=True)
class WorkflowRun:
    """Mutable runtime state for one workflow execution."""

    run_id: WorkflowRunId
    workflow_id: WorkflowId
    workflow_version: str
    status: WorkflowRunStatus = WorkflowRunStatus.PENDING
    parameters: Mapping[str, object] = field(default_factory=dict)
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        validate_non_empty_identifier(str(self.run_id), field_name="run_id")
        validate_non_empty_identifier(str(self.workflow_id), field_name="workflow_id")
        validate_non_empty_identifier(
            self.workflow_version,
            field_name="workflow_version",
        )

        if not isinstance(self.status, WorkflowRunStatus):
            raise TypeError("status must be a WorkflowRunStatus.")

        _ensure_aware_datetime(self.created_at, field_name="created_at")
        _ensure_aware_datetime(self.started_at, field_name="started_at")
        _ensure_aware_datetime(self.finished_at, field_name="finished_at")

        if self.status is WorkflowRunStatus.PENDING:
            if self.started_at is not None or self.finished_at is not None:
                raise ValueError("PENDING WorkflowRun cannot have started_at or finished_at.")
        elif self.status is WorkflowRunStatus.RUNNING:
            if self.finished_at is not None:
                raise ValueError("RUNNING WorkflowRun cannot have finished_at.")
        elif self.status in WORKFLOW_TERMINAL_STATUSES and self.finished_at is None:
            raise ValueError("Terminal WorkflowRun must have finished_at.")

        self.parameters = _freeze_mapping(self.parameters)


@dataclass(slots=True)
class TaskRun:
    """Mutable runtime state for one task inside a workflow run."""

    task_run_id: TaskRunId
    run_id: WorkflowRunId
    task_id: TaskId
    status: TaskRunStatus = TaskRunStatus.PENDING
    skip_reason: SkipReason | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        validate_non_empty_identifier(
            str(self.task_run_id),
            field_name="task_run_id",
        )
        validate_non_empty_identifier(str(self.run_id), field_name="run_id")
        validate_non_empty_identifier(str(self.task_id), field_name="task_id")

        if not isinstance(self.status, TaskRunStatus):
            raise TypeError("status must be a TaskRunStatus.")
        if self.skip_reason is not None and not isinstance(self.skip_reason, SkipReason):
            raise TypeError("skip_reason must be a SkipReason.")

        _ensure_aware_datetime(self.created_at, field_name="created_at")
        _ensure_aware_datetime(self.started_at, field_name="started_at")
        _ensure_aware_datetime(self.finished_at, field_name="finished_at")

        if self.status is TaskRunStatus.SKIPPED:
            if self.skip_reason is None:
                raise ValueError("SKIPPED TaskRun must have skip_reason.")
        elif self.skip_reason is not None:
            raise ValueError("skip_reason is only valid for a SKIPPED TaskRun.")

        if self.status in {TaskRunStatus.PENDING, TaskRunStatus.READY}:
            if self.finished_at is not None:
                raise ValueError(f"{self.status.value} TaskRun cannot have finished_at.")
        elif self.status is TaskRunStatus.RUNNING:
            if self.finished_at is not None:
                raise ValueError("RUNNING TaskRun cannot have finished_at.")
        elif self.status in TASK_TERMINAL_STATUSES and self.finished_at is None:
            raise ValueError("Terminal TaskRun must have finished_at.")


@dataclass(slots=True)
class TaskAttempt:
    """Mutable runtime state for one physical attempt of a task run."""

    attempt_id: TaskAttemptId
    task_run_id: TaskRunId
    attempt_number: int
    status: TaskAttemptStatus = TaskAttemptStatus.RUNNING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_type: str | None = None
    error_message: str | None = None
    error_category: str | None = None
    error_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_identifier(
            str(self.attempt_id),
            field_name="attempt_id",
        )
        validate_non_empty_identifier(
            str(self.task_run_id),
            field_name="task_run_id",
        )
        _validate_positive_integer(
            self.attempt_number,
            field_name="attempt_number",
        )

        if not isinstance(self.status, TaskAttemptStatus):
            raise TypeError("status must be a TaskAttemptStatus.")

        _ensure_aware_datetime(self.started_at, field_name="started_at")
        _ensure_aware_datetime(self.finished_at, field_name="finished_at")

        if self.status is TaskAttemptStatus.RUNNING:
            if self.finished_at is not None:
                raise ValueError("RUNNING TaskAttempt cannot have finished_at.")
        elif self.finished_at is None:
            raise ValueError("Terminal TaskAttempt must have finished_at.")

        self.error_metadata = _freeze_mapping(self.error_metadata)


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    """Immutable fact emitted by the workflow runtime."""

    event_id: RuntimeEventId
    event_type: RuntimeEventType
    run_id: WorkflowRunId
    occurred_at: datetime
    event_sequence: int | None = None
    task_run_id: TaskRunId | None = None
    task_id: TaskId | None = None
    attempt_number: int | None = None
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_identifier(str(self.event_id), field_name="event_id")
        validate_non_empty_identifier(str(self.run_id), field_name="run_id")

        if not isinstance(self.event_type, RuntimeEventType):
            raise TypeError("event_type must be a RuntimeEventType.")

        if self.task_run_id is not None:
            validate_non_empty_identifier(
                str(self.task_run_id),
                field_name="task_run_id",
            )
        if self.task_id is not None:
            validate_non_empty_identifier(str(self.task_id), field_name="task_id")

        _ensure_aware_datetime(self.occurred_at, field_name="occurred_at")

        if self.event_sequence is not None:
            _validate_positive_integer(
                self.event_sequence,
                field_name="event_sequence",
            )
        if self.attempt_number is not None:
            _validate_positive_integer(
                self.attempt_number,
                field_name="attempt_number",
            )

        object.__setattr__(self, "payload", _freeze_mapping(self.payload))


__all__ = [
    "RuntimeEvent",
    "TaskAttempt",
    "TaskRun",
    "WorkflowRun",
]
