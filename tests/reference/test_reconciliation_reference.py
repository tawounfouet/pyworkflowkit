"""M38 reference acceptance for durable external reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pyworkflowkit.adapters.metadata.sqlite import SQLiteMetadataStore
from pyworkflowkit.application.reconciliation import (
    ExternalRunVerifierRegistry,
    ReconciliationDisposition,
    ReconciliationService,
)
from pyworkflowkit.domain.enums import TaskRunStatus, WorkflowRunStatus
from pyworkflowkit.domain.ids import (
    ExternalRunRefId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import ExternalRunRef
from pyworkflowkit.ports.reconciliation import ExternalRunStatus

NOW = datetime(2026, 9, 27, 15, 0, tzinfo=UTC)
OLD = NOW - timedelta(hours=1)


class FixedClock:
    def now(self) -> datetime:
        return NOW


@dataclass
class StaticVerifier:
    provider: str
    status: ExternalRunStatus

    def verify(self, external_ref: ExternalRunRef) -> ExternalRunStatus:
        assert external_ref.external_run_id == "remote-42"
        return self.status


def test_external_completion_is_reconciled_after_sqlite_restart_without_state_mutation(
    tmp_path,
) -> None:
    database = tmp_path / "reconciliation.sqlite3"
    run_id = WorkflowRunId("run-reconcile")
    task_run_id = TaskRunId("task-run-reconcile")

    with SQLiteMetadataStore(database) as store, store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=run_id,
                workflow_id=WorkflowId("workflow.reconciliation"),
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
                task_id=TaskId("remote-task"),
                status=TaskRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("attempt-reconcile"),
                task_run_id=task_run_id,
                attempt_number=1,
                started_at=OLD,
            )
        )
        uow.add_external_run_ref(
            task_run_id=task_run_id,
            external_ref=ExternalRunRef(
                external_ref_id=ExternalRunRefId("external-reconcile"),
                provider="remote-system",
                external_run_id="remote-42",
            ),
        )
        uow.commit()

    registry = ExternalRunVerifierRegistry()
    registry.register(
        StaticVerifier(
            provider="remote-system",
            status=ExternalRunStatus.SUCCEEDED,
        )
    )

    with SQLiteMetadataStore(database) as reopened:
        report = ReconciliationService(
            metadata_store=reopened,
            clock=FixedClock(),
            verifier_registry=registry,
            stale_after=timedelta(minutes=5),
        ).reconcile(run_id)

        assert report.run_id == "run-reconcile"
        assert report.fully_resolved is True
        assert report.requires_manual_action is False
        assert len(report.task_reconciliations) == 1

        task = report.task_reconciliations[0]
        assert task.task_run_id == "task-run-reconcile"
        assert task.disposition is ReconciliationDisposition.CONFIRMED_SUCCEEDED
        assert task.running_attempt_ids == ("attempt-reconcile",)
        assert task.observations[0].status is ExternalRunStatus.SUCCEEDED

        # M38 is still read-only. M39 owns runtime state transitions during resume.
        assert reopened.get_workflow_run(run_id).status is WorkflowRunStatus.RUNNING
        assert reopened.get_task_run(task_run_id).status is TaskRunStatus.RUNNING
        assert reopened.list_task_attempts(task_run_id)[0].status.value == "RUNNING"


def test_external_work_still_running_remains_non_resolved_after_restart(tmp_path) -> None:
    database = tmp_path / "still-running.sqlite3"
    run_id = WorkflowRunId("run-running")
    task_run_id = TaskRunId("task-run-running")

    with SQLiteMetadataStore(database) as store, store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=run_id,
                workflow_id=WorkflowId("workflow.reconciliation"),
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
                task_id=TaskId("remote-task"),
                status=TaskRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("attempt-running"),
                task_run_id=task_run_id,
                attempt_number=1,
                started_at=OLD,
            )
        )
        uow.add_external_run_ref(
            task_run_id=task_run_id,
            external_ref=ExternalRunRef(
                external_ref_id=ExternalRunRefId("external-running"),
                provider="remote-system",
                external_run_id="remote-42",
            ),
        )
        uow.commit()

    registry = ExternalRunVerifierRegistry()
    registry.register(StaticVerifier("remote-system", ExternalRunStatus.RUNNING))

    with SQLiteMetadataStore(database) as reopened:
        report = ReconciliationService(
            metadata_store=reopened,
            clock=FixedClock(),
            verifier_registry=registry,
            stale_after=timedelta(minutes=5),
        ).reconcile(run_id)

        assert report.has_still_running is True
        assert report.fully_resolved is False
        assert report.task_reconciliations[0].disposition is ReconciliationDisposition.STILL_RUNNING
