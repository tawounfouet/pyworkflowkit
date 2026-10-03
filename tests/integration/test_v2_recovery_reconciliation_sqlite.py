"""LOT-11 durable restart acceptance for V2 recovery/reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pyworkflowkit.persistence import SQLiteMetadataStore
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    ExternalRunRef,
    ExternalRunStatus,
    ExternalRunVerifierRegistry,
    ReconciliationService,
    TaskAttempt,
    TaskAttemptId,
    TaskRun,
    TaskRunId,
    WorkflowRun,
    WorkflowRunId,
)
from pyworkflowkit.states import (
    TaskAttemptStateMachine,
    TaskAttemptStatus,
    TaskRunStateMachine,
    TaskRunStatus,
    WorkflowRunStateMachine,
    WorkflowRunStatus,
)

T0 = datetime(2026, 10, 3, 7, 0, tzinfo=UTC)
T1 = T0 + timedelta(seconds=1)
T2 = T0 + timedelta(seconds=2)
T3 = T0 + timedelta(seconds=3)
T4 = T0 + timedelta(seconds=4)


class FixedClock:
    def now(self) -> datetime:
        return T4


@dataclass
class StaticVerifier:
    provider: str
    status: ExternalRunStatus

    def verify(self, external_ref: ExternalRunRef) -> ExternalRunStatus:
        assert external_ref.external_run_id == "REMOTE-42"
        return self.status


def _persist_unknown_outcome(database: Path) -> tuple[WorkflowRunId, TaskRunId, TaskAttemptId]:
    run = WorkflowRun(
        run_id=WorkflowRunId.parse("W-RESTART"),
        workflow_name="restart-demo",
        workflow_version="1",
        definition_fingerprint="sha256:def",
        plan_fingerprint="sha256:plan",
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-RESTART"),
        ),
        created_at=T0,
    )
    task = TaskRun(
        task_run_id=TaskRunId.parse("TR-RESTART"),
        workflow_run_id=run.run_id,
        task_key="remote-job",
        created_at=T0,
    )
    attempt = TaskAttempt(
        attempt_id=TaskAttemptId.parse("TA-RESTART"),
        task_run_id=task.task_run_id,
        attempt_number=1,
        created_at=T0,
    )

    with SQLiteMetadataStore(database, wal=False) as store:
        store.create_workflow_run(run)
        store.create_task_run(task)
        store.append_task_attempt(attempt)

        workflow_states = WorkflowRunStateMachine()
        task_states = TaskRunStateMachine()
        attempt_states = TaskAttemptStateMachine()

        workflow_states.transition(run, WorkflowRunStatus.RUNNING, at=T1)
        store.update_workflow_run(
            run,
            expected_status=WorkflowRunStatus.PENDING,
            transitioned_at=T1,
        )

        task_states.transition(task, TaskRunStatus.READY, at=T1)
        store.update_task_run(
            task,
            expected_status=TaskRunStatus.PENDING,
            transitioned_at=T1,
        )
        task_states.transition(task, TaskRunStatus.RUNNING, at=T2)
        store.update_task_run(
            task,
            expected_status=TaskRunStatus.READY,
            transitioned_at=T2,
        )

        attempt_states.transition(attempt, TaskAttemptStatus.STARTING, at=T1)
        store.update_task_attempt(
            attempt,
            expected_status=TaskAttemptStatus.PENDING,
            transitioned_at=T1,
        )
        attempt_states.transition(attempt, TaskAttemptStatus.RUNNING, at=T2)
        store.update_task_attempt(
            attempt,
            expected_status=TaskAttemptStatus.STARTING,
            transitioned_at=T2,
        )

        store.append_external_run_ref(
            attempt_id=attempt.attempt_id,
            external_ref=ExternalRunRef(
                provider="remote",
                external_run_id="REMOTE-42",
                kind="job",
                correlation_id=run.correlation.correlation_id,
            ),
        )

        attempt_states.transition(
            attempt,
            TaskAttemptStatus.REQUIRES_RECONCILIATION,
            at=T3,
        )
        store.update_task_attempt(
            attempt,
            expected_status=TaskAttemptStatus.RUNNING,
            transitioned_at=T3,
        )
        task_states.transition(task, TaskRunStatus.UNKNOWN_OUTCOME, at=T3)
        store.update_task_run(
            task,
            expected_status=TaskRunStatus.RUNNING,
            transitioned_at=T3,
        )
        workflow_states.transition(run, WorkflowRunStatus.UNKNOWN_OUTCOME, at=T3)
        store.update_workflow_run(
            run,
            expected_status=WorkflowRunStatus.RUNNING,
            transitioned_at=T3,
        )

    return run.run_id, task.task_run_id, attempt.attempt_id


def test_sqlite_restart_reconciles_same_attempt_without_duplicate_execution(
    tmp_path: Path,
) -> None:
    database = tmp_path / "recovery.sqlite3"
    run_id, task_run_id, attempt_id = _persist_unknown_outcome(database)

    registry = ExternalRunVerifierRegistry()
    registry.register(StaticVerifier("remote", ExternalRunStatus.SUCCEEDED))

    with SQLiteMetadataStore(database, wal=False) as reopened:
        service = ReconciliationService(
            metadata=reopened,
            verifier_registry=registry,
            clock=FixedClock(),
        )

        assessment = service.assess(run_id)
        assert assessment.requires_reconciliation is True

        report = service.reconcile(run_id)

        assert report.fully_resolved is True
        assert report.workflow_status_before is WorkflowRunStatus.UNKNOWN_OUTCOME
        assert report.workflow_status_after is WorkflowRunStatus.SUCCEEDED
        assert reopened.get_task_attempt(attempt_id).status is TaskAttemptStatus.SUCCEEDED
        assert reopened.get_task_run(task_run_id).status is TaskRunStatus.SUCCEEDED
        assert len(reopened.list_task_attempts(task_run_id)) == 1

        refs = reopened.list_external_run_refs(attempt_id)
        assert len(refs) == 1
        assert refs[0].external_run_id == "REMOTE-42"

        transitions = reopened.list_state_transitions()
        assert transitions[-3].to_status == TaskAttemptStatus.SUCCEEDED.value
        assert transitions[-2].to_status == TaskRunStatus.SUCCEEDED.value
        assert transitions[-1].to_status == WorkflowRunStatus.SUCCEEDED.value
