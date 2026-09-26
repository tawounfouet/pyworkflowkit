"""Tests for M37 recovery foundation diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.application.recovery import (
    RecoveryInspector,
    RecoveryLiveness,
    ResumeEligibility,
)
from pyworkflowkit.domain.enums import (
    RuntimeEventType,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import (
    ExternalRunRefId,
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import ExternalRunRef

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
OLD = NOW - timedelta(hours=2)
RECENT = NOW - timedelta(seconds=30)


class FixedClock:
    def now(self) -> datetime:
        return NOW


def _inspector(
    store: MemoryMetadataStore,
    *,
    stale_after: timedelta = timedelta(minutes=5),
) -> RecoveryInspector:
    return RecoveryInspector(
        metadata_store=store,
        clock=FixedClock(),
        stale_after=stale_after,
    )


def _persist_run(
    store: MemoryMetadataStore,
    *,
    run_id: str = "run",
    run_status: WorkflowRunStatus = WorkflowRunStatus.RUNNING,
    run_started_at: datetime | None = OLD,
    task_status: TaskRunStatus = TaskRunStatus.RUNNING,
    task_started_at: datetime | None = OLD,
    attempt_status: TaskAttemptStatus | None = TaskAttemptStatus.RUNNING,
    attempt_started_at: datetime | None = OLD,
    attempt_finished_at: datetime | None = None,
    event_at: datetime | None = None,
    external: bool = False,
) -> None:
    workflow_run_id = WorkflowRunId(run_id)
    task_run_id = TaskRunId(f"{run_id}:task")
    run_finished = NOW if run_status in {
        WorkflowRunStatus.SUCCEEDED,
        WorkflowRunStatus.FAILED,
        WorkflowRunStatus.CANCELLED,
    } else None
    task_finished = NOW if task_status in {
        TaskRunStatus.SUCCEEDED,
        TaskRunStatus.FAILED,
        TaskRunStatus.SKIPPED,
        TaskRunStatus.CANCELLED,
    } else None

    with store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=workflow_run_id,
                workflow_id=WorkflowId("workflow"),
                workflow_version="1",
                status=run_status,
                created_at=run_started_at,
                started_at=run_started_at if run_status is not WorkflowRunStatus.PENDING else None,
                finished_at=run_finished,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=task_run_id,
                run_id=workflow_run_id,
                task_id=TaskId("task"),
                status=task_status,
                created_at=task_started_at,
                started_at=task_started_at
                if task_status not in {TaskRunStatus.PENDING, TaskRunStatus.READY}
                else None,
                finished_at=task_finished,
                skip_reason=None,
            )
        )
        if attempt_status is not None:
            terminal_attempt = attempt_status is not TaskAttemptStatus.RUNNING
            uow.add_task_attempt(
                TaskAttempt(
                    attempt_id=TaskAttemptId(f"{run_id}:attempt-1"),
                    task_run_id=task_run_id,
                    attempt_number=1,
                    status=attempt_status,
                    started_at=attempt_started_at,
                    finished_at=(
                        attempt_finished_at
                        if terminal_attempt
                        else None
                    ),
                )
            )
        if event_at is not None:
            uow.add_event(
                RuntimeEvent(
                    event_id=RuntimeEventId(f"{run_id}:event-1"),
                    event_type=RuntimeEventType.TASK_STARTED,
                    run_id=workflow_run_id,
                    occurred_at=event_at,
                    event_sequence=1,
                    task_run_id=task_run_id,
                    task_id=TaskId("task"),
                    attempt_number=1,
                )
            )
        if external:
            uow.add_external_run_ref(
                task_run_id=task_run_id,
                external_ref=ExternalRunRef(
                    external_ref_id=ExternalRunRefId(f"{run_id}:external"),
                    provider="remote",
                    external_run_id=f"remote-{run_id}",
                ),
            )
        uow.commit()


def test_terminal_run_is_not_recovery_candidate() -> None:
    store = MemoryMetadataStore()
    _persist_run(
        store,
        run_status=WorkflowRunStatus.SUCCEEDED,
        task_status=TaskRunStatus.SUCCEEDED,
        attempt_status=TaskAttemptStatus.SUCCEEDED,
        attempt_finished_at=NOW,
    )

    assessment = _inspector(store).assess(WorkflowRunId("run"))

    assert assessment.liveness is RecoveryLiveness.TERMINAL
    assert assessment.resume_eligibility is ResumeEligibility.NOT_ELIGIBLE
    assert assessment.stale_candidate is False
    assert "workflow_is_terminal" in assessment.reasons


def test_recent_runtime_event_keeps_nonterminal_run_active() -> None:
    store = MemoryMetadataStore()
    _persist_run(store, event_at=RECENT)

    assessment = _inspector(store).assess(WorkflowRunId("run"))

    assert assessment.liveness is RecoveryLiveness.ACTIVE
    assert assessment.last_evidence_at == RECENT
    assert assessment.resume_eligibility is ResumeEligibility.NOT_ELIGIBLE
    assert assessment.running_attempt_ids == ("run:attempt-1",)


def test_old_evidence_marks_run_as_stale_candidate() -> None:
    store = MemoryMetadataStore()
    _persist_run(
        store,
        task_status=TaskRunStatus.READY,
        task_started_at=OLD,
        attempt_status=None,
    )

    assessment = _inspector(store).assess(WorkflowRunId("run"))

    assert assessment.liveness is RecoveryLiveness.STALE_CANDIDATE
    assert assessment.resume_eligibility is ResumeEligibility.ELIGIBLE
    assert assessment.requires_reconciliation is False
    assert assessment.running_attempt_ids == ()


def test_running_attempt_requires_reconciliation_before_future_resume() -> None:
    store = MemoryMetadataStore()
    _persist_run(store)

    assessment = _inspector(store).assess(WorkflowRunId("run"))

    assert assessment.liveness is RecoveryLiveness.STALE_CANDIDATE
    assert assessment.resume_eligibility is ResumeEligibility.REQUIRES_RECONCILIATION
    assert assessment.requires_reconciliation is True
    assert "running_attempt_requires_reconciliation" in assessment.reasons


def test_external_work_requires_reconciliation_before_future_resume() -> None:
    store = MemoryMetadataStore()
    _persist_run(
        store,
        task_status=TaskRunStatus.READY,
        task_started_at=OLD,
        attempt_status=None,
        external=True,
    )

    assessment = _inspector(store).assess(WorkflowRunId("run"))

    assert assessment.resume_eligibility is ResumeEligibility.REQUIRES_RECONCILIATION
    assert assessment.external_run_ref_count == 1
    assert "external_work_requires_reconciliation" in assessment.reasons


def test_task_run_id_is_stable_idempotency_key_across_attempts() -> None:
    store = MemoryMetadataStore()
    _persist_run(
        store,
        task_status=TaskRunStatus.READY,
        task_started_at=OLD,
        attempt_status=TaskAttemptStatus.FAILED,
        attempt_finished_at=OLD + timedelta(minutes=1),
    )

    task_run_id = TaskRunId("run:task")
    with store.unit_of_work() as uow:
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("run:attempt-2"),
                task_run_id=task_run_id,
                attempt_number=2,
                status=TaskAttemptStatus.FAILED,
                started_at=OLD + timedelta(minutes=2),
                finished_at=OLD + timedelta(minutes=3),
            )
        )
        uow.commit()

    assessment = _inspector(store).assess(WorkflowRunId("run"))

    assert len(assessment.idempotency) == 1
    metadata = assessment.idempotency[0]
    assert metadata.task_run_id == "run:task"
    assert metadata.idempotency_key == "run:task"
    assert metadata.attempt_count == 2


def test_find_stale_candidates_excludes_recent_and_terminal_runs() -> None:
    store = MemoryMetadataStore()
    _persist_run(
        store,
        run_id="stale",
        task_status=TaskRunStatus.READY,
        task_started_at=OLD,
        attempt_status=None,
    )
    _persist_run(store, run_id="active", event_at=RECENT)
    _persist_run(
        store,
        run_id="done",
        run_status=WorkflowRunStatus.SUCCEEDED,
        task_status=TaskRunStatus.SUCCEEDED,
        attempt_status=TaskAttemptStatus.SUCCEEDED,
        attempt_finished_at=NOW,
    )

    candidates = _inspector(store).find_stale_candidates()

    assert tuple(candidate.run_id for candidate in candidates) == ("stale",)


def test_missing_timestamp_evidence_is_unknown_not_implicitly_stale() -> None:
    store = MemoryMetadataStore()
    _persist_run(
        store,
        run_started_at=None,
        task_status=TaskRunStatus.READY,
        task_started_at=None,
        attempt_status=None,
    )

    assessment = _inspector(store).assess(WorkflowRunId("run"))

    assert assessment.liveness is RecoveryLiveness.UNKNOWN
    assert assessment.resume_eligibility is ResumeEligibility.NOT_ELIGIBLE
    assert "missing_timestamp_evidence" in assessment.reasons


def test_future_evidence_is_unknown_not_stale() -> None:
    store = MemoryMetadataStore()
    _persist_run(store, event_at=NOW + timedelta(minutes=1))

    assessment = _inspector(store).assess(WorkflowRunId("run"))

    assert assessment.liveness is RecoveryLiveness.UNKNOWN
    assert "latest_evidence_is_in_the_future" in assessment.reasons


@pytest.mark.parametrize(
    "stale_after",
    [timedelta(0), timedelta(seconds=-1)],
)
def test_recovery_inspector_rejects_non_positive_stale_threshold(
    stale_after: timedelta,
) -> None:
    with pytest.raises(ValueError, match="stale_after"):
        RecoveryInspector(
            metadata_store=MemoryMetadataStore(),
            clock=FixedClock(),
            stale_after=stale_after,
        )


def test_recovery_inspector_rejects_naive_clock() -> None:
    class NaiveClock:
        def now(self) -> datetime:
            return datetime(2026, 9, 27, 12, 0)

    store = MemoryMetadataStore()
    _persist_run(store)

    with pytest.raises(ValueError, match="timezone-aware"):
        RecoveryInspector(
            metadata_store=store,
            clock=NaiveClock(),
            stale_after=timedelta(minutes=5),
        ).assess(WorkflowRunId("run"))
