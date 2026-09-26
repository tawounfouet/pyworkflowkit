"""M37 reference acceptance for durable recovery diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pyworkflowkit.adapters.metadata.sqlite import SQLiteMetadataStore
from pyworkflowkit.application.recovery import (
    RecoveryInspector,
    RecoveryLiveness,
    ResumeEligibility,
)
from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import RuntimeEventType, TaskRunStatus, WorkflowRunStatus
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
OLD = NOW - timedelta(hours=1)


class FixedClock:
    def now(self) -> datetime:
        return NOW


def test_persisted_crash_state_is_detected_after_sqlite_restart_without_mutation(
    tmp_path,
) -> None:
    database = tmp_path / "recovery.sqlite3"
    run_id = WorkflowRunId("run-crashed")
    task_run_id = TaskRunId("task-run-crashed")

    with SQLiteMetadataStore(database) as store, store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=run_id,
                workflow_id=WorkflowId("workflow.recovery"),
                workflow_version="1",
                status=WorkflowRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=task_run_id,
                run_id=run_id,
                task_id=TaskId("external-task"),
                status=TaskRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("attempt-crashed"),
                task_run_id=task_run_id,
                attempt_number=1,
                started_at=OLD,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("event-started"),
                event_type=RuntimeEventType.TASK_STARTED,
                run_id=run_id,
                occurred_at=OLD,
                event_sequence=1,
                task_run_id=task_run_id,
                task_id=TaskId("external-task"),
                attempt_number=1,
            )
        )
        uow.add_external_run_ref(
            task_run_id=task_run_id,
            external_ref=ExternalRunRef(
                external_ref_id=ExternalRunRefId("external-crashed"),
                provider="remote-system",
                external_run_id="remote-123",
            ),
        )
        uow.commit()

    with SQLiteMetadataStore(database) as reopened:
        assessment = RecoveryInspector(
            metadata_store=reopened,
            clock=FixedClock(),
            stale_after=timedelta(minutes=5),
        ).assess(run_id)

        assert assessment.liveness is RecoveryLiveness.STALE_CANDIDATE
        assert assessment.resume_eligibility is ResumeEligibility.REQUIRES_RECONCILIATION
        assert assessment.running_task_run_ids == ("task-run-crashed",)
        assert assessment.running_attempt_ids == ("attempt-crashed",)
        assert assessment.external_run_ref_count == 1
        assert assessment.unresolved_external_run_ref_count == 1
        assert assessment.idempotency[0].idempotency_key == "task-run-crashed"

        # M37 is diagnostic only: it must not silently recover or alter persisted state.
        assert reopened.get_workflow_run(run_id).status is WorkflowRunStatus.RUNNING
        assert reopened.get_task_run(task_run_id).status is TaskRunStatus.RUNNING


def test_stale_candidate_without_ambiguous_work_is_structurally_resume_eligible(
    tmp_path,
) -> None:
    database = tmp_path / "eligible.sqlite3"
    run_id = WorkflowRunId("run-eligible")
    task_run_id = TaskRunId("task-run-eligible")

    with SQLiteMetadataStore(database) as store, store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=run_id,
                workflow_id=WorkflowId("workflow.recovery"),
                workflow_version="1",
                status=WorkflowRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=task_run_id,
                run_id=run_id,
                task_id=TaskId("pending-work"),
                status=TaskRunStatus.READY,
                created_at=OLD,
            )
        )
        uow.commit()

        assessment = RecoveryInspector(
            metadata_store=store,
            clock=FixedClock(),
            stale_after=timedelta(minutes=5),
        ).assess(run_id)

        assert assessment.liveness is RecoveryLiveness.STALE_CANDIDATE
        assert assessment.resume_eligibility is ResumeEligibility.ELIGIBLE
        assert assessment.requires_reconciliation is False
        assert assessment.idempotency[0].idempotency_key == "task-run-eligible"



def test_workflow_runtime_exposes_read_only_recovery_diagnostics() -> None:
    runtime = WorkflowRuntime()
    runtime.register("handlers:done", lambda: "done")
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("workflow.facade-recovery"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("done"),
                handler_ref="handlers:done",
            ),
        ),
    )

    run = runtime.run(workflow)
    assessment = runtime.recovery_assessment(run.run_id, stale_after_seconds=300)

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert assessment.liveness is RecoveryLiveness.TERMINAL
    assert assessment.resume_eligibility is ResumeEligibility.NOT_ELIGIBLE
    assert runtime.stale_run_candidates(stale_after_seconds=300) == ()
