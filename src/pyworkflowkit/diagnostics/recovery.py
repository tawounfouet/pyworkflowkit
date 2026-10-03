"""Read-only V2 recovery inspection over persisted runtime evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pyworkflowkit.persistence import MetadataStore
from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId
from pyworkflowkit.states import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus
from pyworkflowkit.states.enums import (
    TASK_ATTEMPT_TERMINAL_STATUSES,
    TASK_RUN_TERMINAL_STATUSES,
    WORKFLOW_TERMINAL_STATUSES,
)


class RecoveryDisposition(StrEnum):
    """Conservative next action derived only from durable evidence."""

    NO_ACTION = "no_action"
    READY = "ready"
    REQUIRES_RECONCILIATION = "requires_reconciliation"
    MANUAL_REQUIRED = "manual_required"


@dataclass(frozen=True, slots=True)
class TaskRecoveryAssessment:
    """Recovery evidence for one persisted TaskRun."""

    task_run_id: TaskRunId
    task_key: str
    task_status: TaskRunStatus
    latest_attempt_id: TaskAttemptId | None
    latest_attempt_status: TaskAttemptStatus | None
    external_run_ref_count: int
    disposition: RecoveryDisposition
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RecoveryAssessment:
    """Read-only recovery assessment for one WorkflowRun."""

    workflow_run_id: WorkflowRunId
    workflow_status: WorkflowRunStatus
    task_assessments: tuple[TaskRecoveryAssessment, ...]
    disposition: RecoveryDisposition
    reasons: tuple[str, ...] = ()

    @property
    def requires_reconciliation(self) -> bool:
        return self.disposition is RecoveryDisposition.REQUIRES_RECONCILIATION

    @property
    def requires_manual_action(self) -> bool:
        return self.disposition is RecoveryDisposition.MANUAL_REQUIRED


class RecoveryInspector:
    """Classify durable V2 runtime evidence without mutating it."""

    def __init__(self, *, metadata: MetadataStore) -> None:
        if not isinstance(metadata, MetadataStore):
            raise TypeError("metadata must satisfy the V2 MetadataStore Protocol")
        self._metadata = metadata

    def assess(self, workflow_run_id: WorkflowRunId) -> RecoveryAssessment:
        run = self._metadata.get_workflow_run(workflow_run_id)
        task_assessments = tuple(
            self._assess_task(task_run.task_run_id)
            for task_run in self._metadata.list_task_runs(workflow_run_id)
        )

        if run.status in WORKFLOW_TERMINAL_STATUSES:
            disposition = RecoveryDisposition.NO_ACTION
            reasons = ("workflow_is_terminal",)
        elif any(
            item.disposition is RecoveryDisposition.MANUAL_REQUIRED for item in task_assessments
        ):
            disposition = RecoveryDisposition.MANUAL_REQUIRED
            reasons = ("at_least_one_task_requires_manual_recovery",)
        elif any(
            item.disposition is RecoveryDisposition.REQUIRES_RECONCILIATION
            for item in task_assessments
        ):
            disposition = RecoveryDisposition.REQUIRES_RECONCILIATION
            reasons = ("at_least_one_task_requires_reconciliation",)
        else:
            disposition = RecoveryDisposition.READY
            reasons = ("durable_state_has_no_ambiguous_active_attempt",)

        return RecoveryAssessment(
            workflow_run_id=run.run_id,
            workflow_status=run.status,
            task_assessments=task_assessments,
            disposition=disposition,
            reasons=reasons,
        )

    def discover(self) -> tuple[RecoveryAssessment, ...]:
        """Return every non-terminal durable run in deterministic identity order."""

        return tuple(
            self.assess(run.run_id) for run in self._metadata.list_unfinished_workflow_runs()
        )

    def _assess_task(self, task_run_id: TaskRunId) -> TaskRecoveryAssessment:
        task_run = self._metadata.get_task_run(task_run_id)
        attempts = self._metadata.list_task_attempts(task_run_id)
        latest = attempts[-1] if attempts else None

        if task_run.status in TASK_RUN_TERMINAL_STATUSES:
            return TaskRecoveryAssessment(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                task_status=task_run.status,
                latest_attempt_id=latest.attempt_id if latest is not None else None,
                latest_attempt_status=latest.status if latest is not None else None,
                external_run_ref_count=0,
                disposition=RecoveryDisposition.NO_ACTION,
                reasons=("task_is_terminal",),
            )

        if latest is None:
            return TaskRecoveryAssessment(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                task_status=task_run.status,
                latest_attempt_id=None,
                latest_attempt_status=None,
                external_run_ref_count=0,
                disposition=RecoveryDisposition.READY,
                reasons=("task_has_not_started_an_attempt",),
            )

        refs = self._metadata.list_external_run_refs(latest.attempt_id)
        if latest.status in TASK_ATTEMPT_TERMINAL_STATUSES:
            return TaskRecoveryAssessment(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                task_status=task_run.status,
                latest_attempt_id=latest.attempt_id,
                latest_attempt_status=latest.status,
                external_run_ref_count=len(refs),
                disposition=RecoveryDisposition.REQUIRES_RECONCILIATION,
                reasons=("task_state_lags_terminal_attempt_evidence",),
            )

        if refs:
            return TaskRecoveryAssessment(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                task_status=task_run.status,
                latest_attempt_id=latest.attempt_id,
                latest_attempt_status=latest.status,
                external_run_ref_count=len(refs),
                disposition=RecoveryDisposition.REQUIRES_RECONCILIATION,
                reasons=("non_terminal_attempt_has_external_execution_evidence",),
            )

        if latest.status in {
            TaskAttemptStatus.PENDING,
            TaskAttemptStatus.STARTING,
            TaskAttemptStatus.RUNNING,
            TaskAttemptStatus.CANCELLATION_REQUESTED,
            TaskAttemptStatus.CANCELLATION_UNCONFIRMED,
            TaskAttemptStatus.UNKNOWN_OUTCOME,
            TaskAttemptStatus.REQUIRES_RECONCILIATION,
        }:
            return TaskRecoveryAssessment(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                task_status=task_run.status,
                latest_attempt_id=latest.attempt_id,
                latest_attempt_status=latest.status,
                external_run_ref_count=0,
                disposition=RecoveryDisposition.MANUAL_REQUIRED,
                reasons=("non_terminal_attempt_has_no_external_reconciliation_evidence",),
            )

        return TaskRecoveryAssessment(
            task_run_id=task_run.task_run_id,
            task_key=task_run.task_key,
            task_status=task_run.status,
            latest_attempt_id=latest.attempt_id,
            latest_attempt_status=latest.status,
            external_run_ref_count=len(refs),
            disposition=RecoveryDisposition.MANUAL_REQUIRED,
            reasons=("persisted_task_state_is_not_recoverable_automatically",),
        )


__all__ = [
    "RecoveryAssessment",
    "RecoveryDisposition",
    "RecoveryInspector",
    "TaskRecoveryAssessment",
]
