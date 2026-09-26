"""M39 reference acceptance for durable same-run resume."""

from __future__ import annotations

from datetime import UTC, datetime

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
from pyworkflowkit.ports.executor import RunContext

OLD = datetime(2020, 1, 1, 12, 0, tzinfo=UTC)


def test_acc_recovery_002_resumes_same_run_after_sqlite_restart(tmp_path) -> None:
    database = tmp_path / "resume.sqlite3"
    run_id = WorkflowRunId("run-resume")
    a_run_id = TaskRunId("run-resume:A")
    b_run_id = TaskRunId("run-resume:B")

    with SQLiteMetadataStore(database, wal=False) as store, store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=run_id,
                workflow_id=WorkflowId("workflow.resume"),
                workflow_version="1",
                status=WorkflowRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=a_run_id,
                run_id=run_id,
                task_id=TaskId("A"),
                status=TaskRunStatus.SUCCEEDED,
                created_at=OLD,
                started_at=OLD,
                finished_at=OLD,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("run-resume:A:attempt-1"),
                task_run_id=a_run_id,
                attempt_number=1,
                status=TaskAttemptStatus.SUCCEEDED,
                started_at=OLD,
                finished_at=OLD,
            )
        )
        uow.add_task_output_checkpoint(
            task_run_id=a_run_id,
            output={"value": 21},
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=b_run_id,
                run_id=run_id,
                task_id=TaskId("B"),
                status=TaskRunStatus.PENDING,
                created_at=OLD,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("run-resume:event-1"),
                event_type=RuntimeEventType.WORKFLOW_STARTED,
                run_id=run_id,
                occurred_at=OLD,
                event_sequence=1,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("run-resume:event-2"),
                event_type=RuntimeEventType.TASK_SUCCEEDED,
                run_id=run_id,
                occurred_at=OLD,
                event_sequence=2,
                task_run_id=a_run_id,
                task_id=TaskId("A"),
                attempt_number=1,
            )
        )
        uow.commit()

    calls: list[str] = []
    observed: list[object] = []

    def b_handler(context: RunContext) -> int:
        calls.append("B")
        observed.append(context.dependency_outputs[TaskId("A")])
        upstream = context.dependency_outputs[TaskId("A")]
        assert isinstance(upstream, dict)
        return int(upstream["value"]) * 2

    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("workflow.resume"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("A"),
                handler_ref="handlers:A",
            ),
            TaskDefinition(
                task_id=TaskId("B"),
                handler_ref="handlers:B",
                depends_on=(TaskId("A"),),
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
    # Completed A deliberately has no registered handler. Resume must not re-execute it.
    runtime.register("handlers:B", b_handler)

    resumed = runtime.resume_run(
        workflow,
        run_id,
        stale_after_seconds=1,
    )

    assert resumed.run_id == run_id
    assert resumed.status is WorkflowRunStatus.SUCCEEDED
    assert calls == ["B"]
    assert observed == [{"value": 21}]

    events = runtime.events(run_id)
    assert tuple(event.event_sequence for event in events) == (1, 2, 3, 4, 5, 6)
    assert tuple(event.event_type for event in events[2:]) == (
        RuntimeEventType.TASK_READY,
        RuntimeEventType.TASK_STARTED,
        RuntimeEventType.TASK_SUCCEEDED,
        RuntimeEventType.WORKFLOW_SUCCEEDED,
    )

    with SQLiteMetadataStore(database, wal=False) as reopened:
        assert reopened.get_workflow_run(run_id).status is WorkflowRunStatus.SUCCEEDED
        assert reopened.get_task_run(a_run_id).status is TaskRunStatus.SUCCEEDED
        assert reopened.get_task_run(b_run_id).status is TaskRunStatus.SUCCEEDED
        assert len(reopened.list_task_attempts(a_run_id)) == 1
        b_attempts = reopened.list_task_attempts(b_run_id)
        assert len(b_attempts) == 1
        assert b_attempts[0].status is TaskAttemptStatus.SUCCEEDED
        assert reopened.get_task_output_checkpoint(a_run_id) == {"value": 21}
        assert reopened.get_task_output_checkpoint(b_run_id) == 42
