"""M40 reference acceptance for durable non-blocking retry recovery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pyworkflowkit.adapters.metadata.sqlite import SQLiteMetadataStore
from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.config import MetadataSettings, RuntimeSettings
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    RuntimeEventType,
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
)
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun

OLD = datetime(2020, 1, 1, 12, 0, tzinfo=UTC)


def test_m40_retry_wait_survives_sqlite_restart_and_resumes_next_attempt(tmp_path) -> None:
    database = tmp_path / "retry-wait.sqlite3"
    run_id = WorkflowRunId("run-retry-wait")
    task_run_id = TaskRunId("run-retry-wait:A")
    eligible_at = OLD + timedelta(minutes=2)

    with SQLiteMetadataStore(database, wal=False) as store, store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=run_id,
                workflow_id=WorkflowId("workflow.retry"),
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
                task_id=TaskId("A"),
                status=TaskRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("run-retry-wait:A:attempt-1"),
                task_run_id=task_run_id,
                attempt_number=1,
                status=TaskAttemptStatus.FAILED,
                started_at=OLD,
                finished_at=OLD + timedelta(minutes=1),
                error_type="RuntimeError",
                error_message="temporary",
                error_category="RuntimeError",
                retry_eligible_at=eligible_at,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("run-retry-wait:event-1"),
                event_type=RuntimeEventType.WORKFLOW_STARTED,
                run_id=run_id,
                occurred_at=OLD,
                event_sequence=1,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("run-retry-wait:event-2"),
                event_type=RuntimeEventType.TASK_STARTED,
                run_id=run_id,
                occurred_at=OLD,
                event_sequence=2,
                task_run_id=task_run_id,
                task_id=TaskId("A"),
                attempt_number=1,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("run-retry-wait:event-3"),
                event_type=RuntimeEventType.TASK_RETRYING,
                run_id=run_id,
                occurred_at=OLD + timedelta(minutes=1),
                event_sequence=3,
                task_run_id=task_run_id,
                task_id=TaskId("A"),
                attempt_number=1,
                payload={
                    "retry_eligible_at": eligible_at.isoformat(),
                    "next_attempt_number": 2,
                },
            )
        )
        uow.commit()

    calls = 0

    def handler() -> str:
        nonlocal calls
        calls += 1
        return "recovered"

    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("workflow.retry"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("A"),
                handler_ref="handlers:A",
            ),
        ),
    )
    runtime = WorkflowRuntime(
        RuntimeSettings(
            metadata=MetadataSettings(
                backend="sqlite",
                sqlite_path=database,
                sqlite_wal=False,
            )
        )
    )
    runtime.register("handlers:A", handler)

    assessment = runtime.recovery_assessment(run_id, stale_after_seconds=1)
    assert assessment.retry_waiting_task_run_ids == (str(task_run_id),)
    assert assessment.running_attempt_ids == ()
    assert assessment.requires_reconciliation is False

    resumed = runtime.resume_run(
        workflow,
        run_id,
        stale_after_seconds=1,
    )

    assert resumed.run_id == run_id
    assert resumed.status is WorkflowRunStatus.SUCCEEDED
    assert calls == 1

    events = runtime.events(run_id)
    assert tuple(event.event_sequence for event in events) == (1, 2, 3, 4, 5, 6)
    assert tuple(event.event_type for event in events[3:]) == (
        RuntimeEventType.TASK_STARTED,
        RuntimeEventType.TASK_SUCCEEDED,
        RuntimeEventType.WORKFLOW_SUCCEEDED,
    )

    with SQLiteMetadataStore(database, wal=False) as reopened:
        attempts = reopened.list_task_attempts(task_run_id)
        assert tuple(attempt.attempt_number for attempt in attempts) == (1, 2)
        assert attempts[0].retry_eligible_at == eligible_at
        assert attempts[1].status is TaskAttemptStatus.SUCCEEDED
        assert reopened.get_task_run(task_run_id).status is TaskRunStatus.SUCCEEDED
