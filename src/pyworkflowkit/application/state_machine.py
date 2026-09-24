"""Runtime state-transition authority for PyWorkflowKit."""

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType

from pyworkflowkit.domain.enums import (
    ATTEMPT_TERMINAL_STATUSES,
    TASK_TERMINAL_STATUSES,
    WORKFLOW_TERMINAL_STATUSES,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.runtime import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.errors import InvalidStateTransitionError, TerminalStateError


def _ensure_aware_datetime(value: datetime, *, field_name: str = "at") -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def _raise_invalid_transition(
    *,
    entity_type: str,
    entity_id: str,
    current_status: str,
    target_status: str,
    is_terminal: bool,
) -> None:
    error_type = TerminalStateError if is_terminal else InvalidStateTransitionError
    raise error_type(
        entity_type=entity_type,
        entity_id=entity_id,
        current_status=current_status,
        target_status=target_status,
    )


class RunStateMachine:
    """Apply legal state transitions to mutable runtime entities."""

    def start_workflow(self, run: WorkflowRun, *, at: datetime) -> None:
        _ensure_aware_datetime(at)
        self._ensure_workflow_transition(
            run,
            target=WorkflowRunStatus.RUNNING,
            allowed_from={WorkflowRunStatus.PENDING},
        )
        run.status = WorkflowRunStatus.RUNNING
        run.started_at = at
        run.finished_at = None

    def succeed_workflow(self, run: WorkflowRun, *, at: datetime) -> None:
        self._finish_workflow(run, target=WorkflowRunStatus.SUCCEEDED, at=at)

    def fail_workflow(self, run: WorkflowRun, *, at: datetime) -> None:
        self._finish_workflow(run, target=WorkflowRunStatus.FAILED, at=at)

    def cancel_workflow(self, run: WorkflowRun, *, at: datetime) -> None:
        self._finish_workflow(run, target=WorkflowRunStatus.CANCELLED, at=at)

    def mark_task_ready(self, task_run: TaskRun) -> None:
        self._ensure_task_transition(
            task_run,
            target=TaskRunStatus.READY,
            allowed_from={TaskRunStatus.PENDING},
        )
        task_run.status = TaskRunStatus.READY

    def start_task(self, task_run: TaskRun, *, at: datetime) -> None:
        _ensure_aware_datetime(at)
        self._ensure_task_transition(
            task_run,
            target=TaskRunStatus.RUNNING,
            allowed_from={TaskRunStatus.READY},
        )
        task_run.status = TaskRunStatus.RUNNING
        task_run.started_at = at
        task_run.finished_at = None
        task_run.skip_reason = None

    def succeed_task(self, task_run: TaskRun, *, at: datetime) -> None:
        self._finish_task(task_run, target=TaskRunStatus.SUCCEEDED, at=at)

    def fail_task(self, task_run: TaskRun, *, at: datetime) -> None:
        self._finish_task(task_run, target=TaskRunStatus.FAILED, at=at)

    def skip_task(
        self,
        task_run: TaskRun,
        *,
        reason: SkipReason,
        at: datetime,
    ) -> None:
        _ensure_aware_datetime(at)
        if not isinstance(reason, SkipReason):
            raise TypeError("reason must be a SkipReason.")
        self._ensure_task_transition(
            task_run,
            target=TaskRunStatus.SKIPPED,
            allowed_from={TaskRunStatus.PENDING, TaskRunStatus.READY},
        )
        task_run.status = TaskRunStatus.SKIPPED
        task_run.skip_reason = reason
        task_run.finished_at = at

    def cancel_task(self, task_run: TaskRun, *, at: datetime) -> None:
        _ensure_aware_datetime(at)
        self._ensure_task_transition(
            task_run,
            target=TaskRunStatus.CANCELLED,
            allowed_from={
                TaskRunStatus.PENDING,
                TaskRunStatus.READY,
                TaskRunStatus.RUNNING,
            },
        )
        task_run.status = TaskRunStatus.CANCELLED
        task_run.finished_at = at
        task_run.skip_reason = None

    def succeed_attempt(self, attempt: TaskAttempt, *, at: datetime) -> None:
        _ensure_aware_datetime(at)
        self._ensure_attempt_transition(
            attempt,
            target=TaskAttemptStatus.SUCCEEDED,
        )
        attempt.status = TaskAttemptStatus.SUCCEEDED
        attempt.finished_at = at
        attempt.error_type = None
        attempt.error_message = None
        attempt.error_category = None
        attempt.error_metadata = MappingProxyType({})

    def fail_attempt(
        self,
        attempt: TaskAttempt,
        *,
        at: datetime,
        error_type: str,
        error_message: str,
        error_category: str | None = None,
        error_metadata: Mapping[str, object] | None = None,
    ) -> None:
        _ensure_aware_datetime(at)
        if not error_type.strip():
            raise ValueError("error_type must not be empty.")
        if not error_message.strip():
            raise ValueError("error_message must not be empty.")
        if error_category is not None and not error_category.strip():
            raise ValueError("error_category must not be empty when provided.")

        self._ensure_attempt_transition(
            attempt,
            target=TaskAttemptStatus.FAILED,
        )
        attempt.status = TaskAttemptStatus.FAILED
        attempt.finished_at = at
        attempt.error_type = error_type
        attempt.error_message = error_message
        attempt.error_category = error_category
        attempt.error_metadata = MappingProxyType(dict(error_metadata or {}))

    def cancel_attempt(self, attempt: TaskAttempt, *, at: datetime) -> None:
        _ensure_aware_datetime(at)
        self._ensure_attempt_transition(
            attempt,
            target=TaskAttemptStatus.CANCELLED,
        )
        attempt.status = TaskAttemptStatus.CANCELLED
        attempt.finished_at = at

    def _finish_workflow(
        self,
        run: WorkflowRun,
        *,
        target: WorkflowRunStatus,
        at: datetime,
    ) -> None:
        _ensure_aware_datetime(at)
        self._ensure_workflow_transition(
            run,
            target=target,
            allowed_from={WorkflowRunStatus.RUNNING},
        )
        run.status = target
        run.finished_at = at

    def _finish_task(
        self,
        task_run: TaskRun,
        *,
        target: TaskRunStatus,
        at: datetime,
    ) -> None:
        _ensure_aware_datetime(at)
        self._ensure_task_transition(
            task_run,
            target=target,
            allowed_from={TaskRunStatus.RUNNING},
        )
        task_run.status = target
        task_run.finished_at = at
        task_run.skip_reason = None

    @staticmethod
    def _ensure_workflow_transition(
        run: WorkflowRun,
        *,
        target: WorkflowRunStatus,
        allowed_from: set[WorkflowRunStatus],
    ) -> None:
        if run.status not in allowed_from:
            _raise_invalid_transition(
                entity_type="WorkflowRun",
                entity_id=str(run.run_id),
                current_status=run.status.value,
                target_status=target.value,
                is_terminal=run.status in WORKFLOW_TERMINAL_STATUSES,
            )

    @staticmethod
    def _ensure_task_transition(
        task_run: TaskRun,
        *,
        target: TaskRunStatus,
        allowed_from: set[TaskRunStatus],
    ) -> None:
        if task_run.status not in allowed_from:
            _raise_invalid_transition(
                entity_type="TaskRun",
                entity_id=str(task_run.task_run_id),
                current_status=task_run.status.value,
                target_status=target.value,
                is_terminal=task_run.status in TASK_TERMINAL_STATUSES,
            )

    @staticmethod
    def _ensure_attempt_transition(
        attempt: TaskAttempt,
        *,
        target: TaskAttemptStatus,
    ) -> None:
        if attempt.status is not TaskAttemptStatus.RUNNING:
            _raise_invalid_transition(
                entity_type="TaskAttempt",
                entity_id=str(attempt.attempt_id),
                current_status=attempt.status.value,
                target_status=target.value,
                is_terminal=attempt.status in ATTEMPT_TERMINAL_STATUSES,
            )


__all__ = ["RunStateMachine"]
