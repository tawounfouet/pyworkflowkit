"""Validated V2 runtime state-machine services."""

from __future__ import annotations

from datetime import datetime

from pyworkflowkit.diagnostics import FailureEvidence
from pyworkflowkit.errors import InvalidStateTransitionError, TerminalStateError
from pyworkflowkit.runtime.entities import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.states.enums import (
    TASK_ATTEMPT_TERMINAL_STATUSES,
    TASK_RUN_TERMINAL_STATUSES,
    WORKFLOW_TERMINAL_STATUSES,
    BlockReason,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)


def _ensure_aware(at: datetime) -> None:
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("transition timestamp must be timezone-aware")


def _reject(
    *,
    entity_type: str,
    entity_id: str,
    current_status: str,
    target_status: str,
    terminal: bool,
) -> None:
    error_type = TerminalStateError if terminal else InvalidStateTransitionError
    raise error_type(
        entity_type=entity_type,
        entity_id=entity_id,
        current_status=current_status,
        target_status=target_status,
    )


_WORKFLOW_TRANSITIONS: dict[WorkflowRunStatus, frozenset[WorkflowRunStatus]] = {
    WorkflowRunStatus.PENDING: frozenset(
        {
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.CANCELLATION_REQUESTED,
        }
    ),
    WorkflowRunStatus.RUNNING: frozenset(
        {
            WorkflowRunStatus.SUCCEEDED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELLATION_REQUESTED,
            WorkflowRunStatus.TIMED_OUT,
            WorkflowRunStatus.UNKNOWN_OUTCOME,
        }
    ),
    WorkflowRunStatus.CANCELLATION_REQUESTED: frozenset(
        {
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.UNKNOWN_OUTCOME,
        }
    ),
    WorkflowRunStatus.UNKNOWN_OUTCOME: frozenset(
        {
            WorkflowRunStatus.RUNNING,
            WorkflowRunStatus.SUCCEEDED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.TIMED_OUT,
        }
    ),
    WorkflowRunStatus.SUCCEEDED: frozenset(),
    WorkflowRunStatus.FAILED: frozenset(),
    WorkflowRunStatus.CANCELLED: frozenset(),
    WorkflowRunStatus.TIMED_OUT: frozenset(),
}

_TASK_RUN_TRANSITIONS: dict[TaskRunStatus, frozenset[TaskRunStatus]] = {
    TaskRunStatus.PENDING: frozenset(
        {
            TaskRunStatus.READY,
            TaskRunStatus.SKIPPED,
            TaskRunStatus.BLOCKED,
            TaskRunStatus.CANCELLED,
        }
    ),
    TaskRunStatus.READY: frozenset(
        {
            TaskRunStatus.RUNNING,
            TaskRunStatus.SKIPPED,
            TaskRunStatus.BLOCKED,
            TaskRunStatus.CANCELLED,
        }
    ),
    TaskRunStatus.BLOCKED: frozenset(
        {
            TaskRunStatus.READY,
            TaskRunStatus.SKIPPED,
            TaskRunStatus.CANCELLED,
        }
    ),
    TaskRunStatus.RUNNING: frozenset(
        {
            TaskRunStatus.SUCCEEDED,
            TaskRunStatus.FAILED,
            TaskRunStatus.CANCELLED,
            TaskRunStatus.TIMED_OUT,
            TaskRunStatus.TIMED_OUT,
            TaskRunStatus.UNKNOWN_OUTCOME,
        }
    ),
    TaskRunStatus.UNKNOWN_OUTCOME: frozenset(
        {
            TaskRunStatus.RUNNING,
            TaskRunStatus.SUCCEEDED,
            TaskRunStatus.FAILED,
            TaskRunStatus.CANCELLED,
        }
    ),
    TaskRunStatus.SUCCEEDED: frozenset(),
    TaskRunStatus.FAILED: frozenset(),
    TaskRunStatus.SKIPPED: frozenset(),
    TaskRunStatus.CANCELLED: frozenset(),
    TaskRunStatus.TIMED_OUT: frozenset(),
}

_TASK_ATTEMPT_TRANSITIONS: dict[
    TaskAttemptStatus,
    frozenset[TaskAttemptStatus],
] = {
    TaskAttemptStatus.PENDING: frozenset(
        {
            TaskAttemptStatus.STARTING,
            TaskAttemptStatus.CANCELLATION_REQUESTED,
            TaskAttemptStatus.CANCELLED,
        }
    ),
    TaskAttemptStatus.STARTING: frozenset(
        {
            TaskAttemptStatus.RUNNING,
            TaskAttemptStatus.FAILED,
            TaskAttemptStatus.CANCELLATION_REQUESTED,
            TaskAttemptStatus.UNKNOWN_OUTCOME,
        }
    ),
    TaskAttemptStatus.RUNNING: frozenset(
        {
            TaskAttemptStatus.SUCCEEDED,
            TaskAttemptStatus.FAILED,
            TaskAttemptStatus.TIMED_OUT,
            TaskAttemptStatus.CANCELLATION_REQUESTED,
            TaskAttemptStatus.UNKNOWN_OUTCOME,
            TaskAttemptStatus.REQUIRES_RECONCILIATION,
        }
    ),
    TaskAttemptStatus.CANCELLATION_REQUESTED: frozenset(
        {
            TaskAttemptStatus.RUNNING,
            TaskAttemptStatus.CANCELLED,
            TaskAttemptStatus.CANCELLATION_UNCONFIRMED,
            TaskAttemptStatus.SUCCEEDED,
            TaskAttemptStatus.FAILED,
            TaskAttemptStatus.UNKNOWN_OUTCOME,
        }
    ),
    TaskAttemptStatus.CANCELLATION_UNCONFIRMED: frozenset(
        {
            TaskAttemptStatus.REQUIRES_RECONCILIATION,
            TaskAttemptStatus.CANCELLED,
            TaskAttemptStatus.SUCCEEDED,
            TaskAttemptStatus.FAILED,
            TaskAttemptStatus.UNKNOWN_OUTCOME,
        }
    ),
    TaskAttemptStatus.UNKNOWN_OUTCOME: frozenset(
        {
            TaskAttemptStatus.REQUIRES_RECONCILIATION,
            TaskAttemptStatus.SUCCEEDED,
            TaskAttemptStatus.FAILED,
            TaskAttemptStatus.CANCELLED,
        }
    ),
    TaskAttemptStatus.REQUIRES_RECONCILIATION: frozenset(
        {
            TaskAttemptStatus.RUNNING,
            TaskAttemptStatus.SUCCEEDED,
            TaskAttemptStatus.FAILED,
            TaskAttemptStatus.CANCELLED,
            TaskAttemptStatus.UNKNOWN_OUTCOME,
        }
    ),
    TaskAttemptStatus.SUCCEEDED: frozenset(),
    TaskAttemptStatus.FAILED: frozenset(),
    TaskAttemptStatus.TIMED_OUT: frozenset(),
    TaskAttemptStatus.CANCELLED: frozenset(),
}


class WorkflowRunStateMachine:
    """Transition authority for WorkflowRun."""

    def transition(
        self,
        run: WorkflowRun,
        target: WorkflowRunStatus,
        *,
        at: datetime,
        failure: FailureEvidence | None = None,
    ) -> None:
        _ensure_aware(at)
        if not isinstance(target, WorkflowRunStatus):
            raise TypeError("target must be a WorkflowRunStatus")

        allowed = _WORKFLOW_TRANSITIONS[run.status]
        if target not in allowed:
            _reject(
                entity_type="WorkflowRun",
                entity_id=str(run.run_id),
                current_status=run.status.value,
                target_status=target.value,
                terminal=run.status in WORKFLOW_TERMINAL_STATUSES,
            )

        started_at = run.started_at
        if target is WorkflowRunStatus.RUNNING and started_at is None:
            started_at = at

        ended_at = at if target in WORKFLOW_TERMINAL_STATUSES else None
        run._apply_status(
            target,
            started_at=started_at,
            ended_at=ended_at,
            failure=failure,
        )


class TaskRunStateMachine:
    """Transition authority for TaskRun."""

    def transition(
        self,
        task_run: TaskRun,
        target: TaskRunStatus,
        *,
        at: datetime,
        skip_reason: SkipReason | None = None,
        block_reason: BlockReason | None = None,
        failure: FailureEvidence | None = None,
    ) -> None:
        _ensure_aware(at)
        if not isinstance(target, TaskRunStatus):
            raise TypeError("target must be a TaskRunStatus")

        allowed = _TASK_RUN_TRANSITIONS[task_run.status]
        if target not in allowed:
            _reject(
                entity_type="TaskRun",
                entity_id=str(task_run.task_run_id),
                current_status=task_run.status.value,
                target_status=target.value,
                terminal=task_run.status in TASK_RUN_TERMINAL_STATUSES,
            )

        if target is TaskRunStatus.SKIPPED:
            if not isinstance(skip_reason, SkipReason):
                raise ValueError("SKIPPED transition requires skip_reason")
        elif skip_reason is not None:
            raise ValueError("skip_reason is only valid for SKIPPED")

        if target is TaskRunStatus.BLOCKED:
            if not isinstance(block_reason, BlockReason):
                raise ValueError("BLOCKED transition requires block_reason")
        elif block_reason is not None:
            raise ValueError("block_reason is only valid for BLOCKED")

        started_at = task_run.started_at
        if target is TaskRunStatus.RUNNING and started_at is None:
            started_at = at

        ended_at = at if target in TASK_RUN_TERMINAL_STATUSES else None
        task_run._apply_status(
            target,
            started_at=started_at,
            ended_at=ended_at,
            skip_reason=skip_reason,
            block_reason=block_reason,
            failure=failure,
        )


class TaskAttemptStateMachine:
    """Transition authority for TaskAttempt."""

    def transition(
        self,
        attempt: TaskAttempt,
        target: TaskAttemptStatus,
        *,
        at: datetime,
        failure: FailureEvidence | None = None,
    ) -> None:
        _ensure_aware(at)
        if not isinstance(target, TaskAttemptStatus):
            raise TypeError("target must be a TaskAttemptStatus")

        allowed = _TASK_ATTEMPT_TRANSITIONS[attempt.status]
        if target not in allowed:
            _reject(
                entity_type="TaskAttempt",
                entity_id=str(attempt.attempt_id),
                current_status=attempt.status.value,
                target_status=target.value,
                terminal=attempt.status in TASK_ATTEMPT_TERMINAL_STATUSES,
            )

        started_at = attempt.started_at
        if target in {TaskAttemptStatus.STARTING, TaskAttemptStatus.RUNNING} and started_at is None:
            started_at = at

        ended_at = at if target in TASK_ATTEMPT_TERMINAL_STATUSES else None
        attempt._apply_status(
            target,
            started_at=started_at,
            ended_at=ended_at,
            failure=failure,
        )


__all__ = [
    "TaskAttemptStateMachine",
    "TaskRunStateMachine",
    "WorkflowRunStateMachine",
]
