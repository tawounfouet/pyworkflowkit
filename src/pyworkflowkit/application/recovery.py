"""Recovery-foundation diagnostics for persisted workflow runs.

M37 classifies persisted evidence. It deliberately does not mutate runtime state,
reconcile external systems, or resume execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from pyworkflowkit.application.retry import pending_retry_attempt
from pyworkflowkit.domain.enums import (
    WORKFLOW_TERMINAL_STATUSES,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import WorkflowRunId
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.ports.metadata_store import MetadataStore
from pyworkflowkit.ports.runtime import Clock


class RecoveryLiveness(StrEnum):
    """Diagnostic liveness classification for one persisted workflow run."""

    TERMINAL = "terminal"
    ACTIVE = "active"
    STALE_CANDIDATE = "stale_candidate"
    UNKNOWN = "unknown"


class ResumeEligibility(StrEnum):
    """Whether persisted evidence is structurally safe enough for a future resume."""

    NOT_ELIGIBLE = "not_eligible"
    ELIGIBLE = "eligible"
    REQUIRES_RECONCILIATION = "requires_reconciliation"


@dataclass(frozen=True, slots=True)
class TaskIdempotencyMetadata:
    """Stable task-run identity that workloads may use for deduplication."""

    task_id: str
    task_run_id: str
    idempotency_key: str
    attempt_count: int


@dataclass(frozen=True, slots=True)
class RecoveryAssessment:
    """Read-only recovery assessment built from persisted runtime evidence."""

    run_id: str
    workflow_id: str
    workflow_version: str
    workflow_status: WorkflowRunStatus
    observed_at: datetime
    last_evidence_at: datetime | None
    stale_after_seconds: float
    liveness: RecoveryLiveness
    resume_eligibility: ResumeEligibility
    running_task_run_ids: tuple[str, ...]
    running_attempt_ids: tuple[str, ...]
    retry_waiting_task_run_ids: tuple[str, ...]
    next_retry_eligible_at: datetime | None
    external_run_ref_count: int
    unresolved_external_run_ref_count: int
    idempotency: tuple[TaskIdempotencyMetadata, ...]
    reasons: tuple[str, ...]

    @property
    def stale_candidate(self) -> bool:
        return self.liveness is RecoveryLiveness.STALE_CANDIDATE

    @property
    def requires_reconciliation(self) -> bool:
        return self.resume_eligibility is ResumeEligibility.REQUIRES_RECONCILIATION


class RecoveryInspector:
    """Classify persisted runs without performing recovery actions."""

    def __init__(
        self,
        *,
        metadata_store: MetadataStore,
        clock: Clock,
        stale_after: timedelta,
    ) -> None:
        if stale_after <= timedelta(0):
            raise ValueError("stale_after must be greater than zero")
        self._metadata_store = metadata_store
        self._clock = clock
        self._stale_after = stale_after

    def assess(self, run_id: WorkflowRunId) -> RecoveryAssessment:
        """Assess one persisted workflow run."""

        observed_at = self._clock.now()
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("Clock.now() must return a timezone-aware datetime")

        run = self._metadata_store.get_workflow_run(run_id)
        task_runs = tuple(self._metadata_store.list_task_runs(run_id))
        attempts_by_task_run = {
            task_run.task_run_id: tuple(
                self._metadata_store.list_task_attempts(task_run.task_run_id)
            )
            for task_run in task_runs
        }
        events = tuple(self._metadata_store.list_events(run_id))

        latest_evidence = _latest_evidence_at(
            run=run,
            task_runs=task_runs,
            attempts=tuple(
                attempt for attempts in attempts_by_task_run.values() for attempt in attempts
            ),
            events=events,
        )

        retry_waiting = {
            task_run.task_run_id: pending_retry_attempt(
                attempts_by_task_run[task_run.task_run_id]
            )
            for task_run in task_runs
            if task_run.status is TaskRunStatus.RUNNING
        }
        retry_waiting = {
            task_run_id: attempt
            for task_run_id, attempt in retry_waiting.items()
            if attempt is not None
        }
        retry_waiting_task_runs = tuple(
            sorted(str(task_run_id) for task_run_id in retry_waiting)
        )
        retry_eligible_times = tuple(
            attempt.retry_eligible_at
            for attempt in retry_waiting.values()
            if attempt.retry_eligible_at is not None
        )
        next_retry_eligible_at = min(retry_eligible_times) if retry_eligible_times else None

        running_task_runs = tuple(
            sorted(
                str(task_run.task_run_id)
                for task_run in task_runs
                if task_run.status is TaskRunStatus.RUNNING
                and task_run.task_run_id not in retry_waiting
            )
        )
        running_attempts = tuple(
            sorted(
                str(attempt.attempt_id)
                for attempts in attempts_by_task_run.values()
                for attempt in attempts
                if attempt.status is TaskAttemptStatus.RUNNING
            )
        )

        external_refs_by_task_run = {
            task_run.task_run_id: tuple(
                self._metadata_store.list_external_run_refs(task_run.task_run_id)
            )
            for task_run in task_runs
        }
        external_ref_count = sum(len(values) for values in external_refs_by_task_run.values())
        unresolved_external_ref_count = sum(
            len(external_refs_by_task_run[task_run.task_run_id])
            for task_run in task_runs
            if task_run.status
            not in {
                TaskRunStatus.SUCCEEDED,
                TaskRunStatus.FAILED,
                TaskRunStatus.SKIPPED,
                TaskRunStatus.CANCELLED,
            }
        )

        idempotency = tuple(
            TaskIdempotencyMetadata(
                task_id=str(task_run.task_id),
                task_run_id=str(task_run.task_run_id),
                idempotency_key=str(task_run.task_run_id),
                attempt_count=len(attempts_by_task_run[task_run.task_run_id]),
            )
            for task_run in sorted(task_runs, key=lambda value: str(value.task_id))
        )

        liveness, reasons = self._classify_liveness(
            run=run,
            observed_at=observed_at,
            latest_evidence=latest_evidence,
            next_retry_eligible_at=next_retry_eligible_at,
        )
        eligibility, eligibility_reasons = self._classify_resume_eligibility(
            liveness=liveness,
            running_task_run_ids=running_task_runs,
            running_attempt_ids=running_attempts,
            unresolved_external_run_ref_count=unresolved_external_ref_count,
        )

        return RecoveryAssessment(
            run_id=str(run.run_id),
            workflow_id=str(run.workflow_id),
            workflow_version=run.workflow_version,
            workflow_status=run.status,
            observed_at=observed_at,
            last_evidence_at=latest_evidence,
            stale_after_seconds=self._stale_after.total_seconds(),
            liveness=liveness,
            resume_eligibility=eligibility,
            running_task_run_ids=running_task_runs,
            running_attempt_ids=running_attempts,
            retry_waiting_task_run_ids=retry_waiting_task_runs,
            next_retry_eligible_at=next_retry_eligible_at,
            external_run_ref_count=external_ref_count,
            unresolved_external_run_ref_count=unresolved_external_ref_count,
            idempotency=idempotency,
            reasons=tuple((*reasons, *eligibility_reasons)),
        )

    def find_stale_candidates(self) -> tuple[RecoveryAssessment, ...]:
        """Return stale non-terminal runs in deterministic run-id order."""

        assessments = (
            self.assess(run.run_id)
            for run in self._metadata_store.list_workflow_runs()
            if run.status not in WORKFLOW_TERMINAL_STATUSES
        )
        return tuple(
            sorted(
                (
                    assessment
                    for assessment in assessments
                    if assessment.liveness is RecoveryLiveness.STALE_CANDIDATE
                ),
                key=lambda value: value.run_id,
            )
        )

    def _classify_liveness(
        self,
        *,
        run: WorkflowRun,
        observed_at: datetime,
        latest_evidence: datetime | None,
        next_retry_eligible_at: datetime | None,
    ) -> tuple[RecoveryLiveness, tuple[str, ...]]:
        if run.status in WORKFLOW_TERMINAL_STATUSES:
            return RecoveryLiveness.TERMINAL, ("workflow_is_terminal",)

        if next_retry_eligible_at is not None and next_retry_eligible_at > observed_at:
            return RecoveryLiveness.ACTIVE, ("retry_wait_not_yet_eligible",)

        if latest_evidence is None:
            return RecoveryLiveness.UNKNOWN, ("missing_timestamp_evidence",)

        effective_evidence = latest_evidence
        if (
            next_retry_eligible_at is not None
            and next_retry_eligible_at > effective_evidence
        ):
            effective_evidence = next_retry_eligible_at

        age = observed_at - effective_evidence
        if age < timedelta(0):
            return RecoveryLiveness.UNKNOWN, ("latest_evidence_is_in_the_future",)

        if age >= self._stale_after:
            return RecoveryLiveness.STALE_CANDIDATE, ("evidence_older_than_stale_threshold",)

        return RecoveryLiveness.ACTIVE, ("recent_runtime_evidence",)

    @staticmethod
    def _classify_resume_eligibility(
        *,
        liveness: RecoveryLiveness,
        running_task_run_ids: tuple[str, ...],
        running_attempt_ids: tuple[str, ...],
        unresolved_external_run_ref_count: int,
    ) -> tuple[ResumeEligibility, tuple[str, ...]]:
        if liveness is not RecoveryLiveness.STALE_CANDIDATE:
            return ResumeEligibility.NOT_ELIGIBLE, ("run_is_not_a_stale_candidate",)

        reconciliation_reasons: list[str] = []
        if running_task_run_ids:
            reconciliation_reasons.append("running_task_requires_reconciliation")
        if running_attempt_ids:
            reconciliation_reasons.append("running_attempt_requires_reconciliation")
        if unresolved_external_run_ref_count:
            reconciliation_reasons.append("external_work_requires_reconciliation")

        if reconciliation_reasons:
            return (
                ResumeEligibility.REQUIRES_RECONCILIATION,
                tuple(reconciliation_reasons),
            )

        return ResumeEligibility.ELIGIBLE, ("no_ambiguous_running_or_external_work",)


def _latest_evidence_at(
    *,
    run: WorkflowRun,
    task_runs: tuple[TaskRun, ...],
    attempts: tuple[TaskAttempt, ...],
    events: tuple[RuntimeEvent, ...],
) -> datetime | None:
    timestamps = [
        value
        for value in (
            run.created_at,
            run.started_at,
            run.finished_at,
            *(task_run.created_at for task_run in task_runs),
            *(task_run.started_at for task_run in task_runs),
            *(task_run.finished_at for task_run in task_runs),
            *(attempt.started_at for attempt in attempts),
            *(attempt.finished_at for attempt in attempts),
            *(event.occurred_at for event in events),
        )
        if value is not None
    ]
    return max(timestamps) if timestamps else None


__all__ = [
    "RecoveryAssessment",
    "RecoveryInspector",
    "RecoveryLiveness",
    "ResumeEligibility",
    "TaskIdempotencyMetadata",
]
