"""Canonical mutable runtime entities governed by V2 state machines."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pyworkflowkit.diagnostics import FailureEvidence
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId
from pyworkflowkit.states.enums import (
    BlockReason,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)


def _require_text(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _ensure_aware(value: datetime | None, *, field_name: str) -> None:
    if value is None:
        return
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(slots=True)
class WorkflowRun:
    """One execution instance of a WorkflowDefinition or ExecutionPlan."""

    run_id: WorkflowRunId
    workflow_name: str
    workflow_version: str
    definition_fingerprint: str
    plan_fingerprint: str
    correlation: CorrelationContext
    created_at: datetime
    _status: WorkflowRunStatus = field(
        default=WorkflowRunStatus.PENDING,
        repr=False,
    )
    started_at: datetime | None = None
    ended_at: datetime | None = None
    failure: FailureEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, WorkflowRunId):
            raise TypeError("run_id must be a WorkflowRunId")
        for name, value in (
            ("workflow_name", self.workflow_name),
            ("workflow_version", self.workflow_version),
            ("definition_fingerprint", self.definition_fingerprint),
            ("plan_fingerprint", self.plan_fingerprint),
        ):
            _require_text(value, field_name=name)
        if not isinstance(self.correlation, CorrelationContext):
            raise TypeError("correlation must be a CorrelationContext")
        if not isinstance(self._status, WorkflowRunStatus):
            raise TypeError("_status must be a WorkflowRunStatus")
        if self.failure is not None and not isinstance(self.failure, FailureEvidence):
            raise TypeError("failure must be FailureEvidence or None")
        _ensure_aware(self.created_at, field_name="created_at")
        _ensure_aware(self.started_at, field_name="started_at")
        _ensure_aware(self.ended_at, field_name="ended_at")

        if self._status is WorkflowRunStatus.PENDING:
            if self.started_at is not None or self.ended_at is not None:
                raise ValueError("PENDING WorkflowRun cannot have runtime timestamps")
        elif self._status in {
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.CANCELLATION_REQUESTED,
            WorkflowRunStatus.UNKNOWN_OUTCOME,
        }:
            if self.ended_at is not None:
                raise ValueError(f"{self._status.value} WorkflowRun cannot have ended_at")
        elif self.ended_at is None:
            raise ValueError("terminal WorkflowRun must have ended_at")

    @property
    def status(self) -> WorkflowRunStatus:
        return self._status

    def _apply_status(
        self,
        status: WorkflowRunStatus,
        *,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        failure: FailureEvidence | None = None,
    ) -> None:
        self._status = status
        if started_at is not None:
            self.started_at = started_at
        self.ended_at = ended_at
        self.failure = failure


@dataclass(slots=True)
class TaskRun:
    """Logical execution of one task inside one WorkflowRun."""

    task_run_id: TaskRunId
    workflow_run_id: WorkflowRunId
    task_key: str
    created_at: datetime
    _status: TaskRunStatus = field(
        default=TaskRunStatus.PENDING,
        repr=False,
    )
    started_at: datetime | None = None
    ended_at: datetime | None = None
    skip_reason: SkipReason | None = None
    block_reason: BlockReason | None = None
    failure: FailureEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.task_run_id, TaskRunId):
            raise TypeError("task_run_id must be a TaskRunId")
        if not isinstance(self.workflow_run_id, WorkflowRunId):
            raise TypeError("workflow_run_id must be a WorkflowRunId")
        _require_text(self.task_key, field_name="task_key")
        if not isinstance(self._status, TaskRunStatus):
            raise TypeError("_status must be a TaskRunStatus")
        if self.skip_reason is not None and not isinstance(self.skip_reason, SkipReason):
            raise TypeError("skip_reason must be SkipReason or None")
        if self.block_reason is not None and not isinstance(self.block_reason, BlockReason):
            raise TypeError("block_reason must be BlockReason or None")
        if self.failure is not None and not isinstance(self.failure, FailureEvidence):
            raise TypeError("failure must be FailureEvidence or None")
        _ensure_aware(self.created_at, field_name="created_at")
        _ensure_aware(self.started_at, field_name="started_at")
        _ensure_aware(self.ended_at, field_name="ended_at")

        if self._status is TaskRunStatus.SKIPPED:
            if self.skip_reason is None:
                raise ValueError("SKIPPED TaskRun requires skip_reason")
        elif self.skip_reason is not None:
            raise ValueError("skip_reason is only valid for SKIPPED TaskRun")

        if self._status is TaskRunStatus.BLOCKED:
            if self.block_reason is None:
                raise ValueError("BLOCKED TaskRun requires block_reason")
        elif self.block_reason is not None:
            raise ValueError("block_reason is only valid for BLOCKED TaskRun")

        if self._status in {
            TaskRunStatus.PENDING,
            TaskRunStatus.READY,
            TaskRunStatus.BLOCKED,
            TaskRunStatus.RUNNING,
            TaskRunStatus.UNKNOWN_OUTCOME,
        }:
            if self.ended_at is not None:
                raise ValueError(f"{self._status.value} TaskRun cannot have ended_at")
        elif self.ended_at is None:
            raise ValueError("terminal TaskRun must have ended_at")

    @property
    def status(self) -> TaskRunStatus:
        return self._status

    def _apply_status(
        self,
        status: TaskRunStatus,
        *,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        skip_reason: SkipReason | None = None,
        block_reason: BlockReason | None = None,
        failure: FailureEvidence | None = None,
    ) -> None:
        self._status = status
        if started_at is not None:
            self.started_at = started_at
        self.ended_at = ended_at
        self.skip_reason = skip_reason
        self.block_reason = block_reason
        self.failure = failure


@dataclass(slots=True)
class TaskAttempt:
    """One concrete workload attempt belonging to one TaskRun."""

    attempt_id: TaskAttemptId
    task_run_id: TaskRunId
    attempt_number: int
    created_at: datetime
    _status: TaskAttemptStatus = field(
        default=TaskAttemptStatus.PENDING,
        repr=False,
    )
    started_at: datetime | None = None
    ended_at: datetime | None = None
    failure: FailureEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_id, TaskAttemptId):
            raise TypeError("attempt_id must be a TaskAttemptId")
        if not isinstance(self.task_run_id, TaskRunId):
            raise TypeError("task_run_id must be a TaskRunId")
        if isinstance(self.attempt_number, bool) or not isinstance(self.attempt_number, int):
            raise TypeError("attempt_number must be an integer")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be greater than or equal to 1")
        if not isinstance(self._status, TaskAttemptStatus):
            raise TypeError("_status must be a TaskAttemptStatus")
        if self.failure is not None and not isinstance(self.failure, FailureEvidence):
            raise TypeError("failure must be FailureEvidence or None")
        _ensure_aware(self.created_at, field_name="created_at")
        _ensure_aware(self.started_at, field_name="started_at")
        _ensure_aware(self.ended_at, field_name="ended_at")

        if self._status in {
            TaskAttemptStatus.PENDING,
            TaskAttemptStatus.STARTING,
            TaskAttemptStatus.RUNNING,
            TaskAttemptStatus.CANCELLATION_REQUESTED,
            TaskAttemptStatus.CANCELLATION_UNCONFIRMED,
            TaskAttemptStatus.UNKNOWN_OUTCOME,
            TaskAttemptStatus.REQUIRES_RECONCILIATION,
        }:
            if self.ended_at is not None:
                raise ValueError(f"{self._status.value} TaskAttempt cannot have ended_at")
        elif self.ended_at is None:
            raise ValueError("terminal TaskAttempt must have ended_at")

    @property
    def status(self) -> TaskAttemptStatus:
        return self._status

    def _apply_status(
        self,
        status: TaskAttemptStatus,
        *,
        started_at: datetime | None = None,
        ended_at: datetime | None = None,
        failure: FailureEvidence | None = None,
    ) -> None:
        self._status = status
        if started_at is not None:
            self.started_at = started_at
        self.ended_at = ended_at
        self.failure = failure


__all__ = [
    "TaskAttempt",
    "TaskRun",
    "WorkflowRun",
]
