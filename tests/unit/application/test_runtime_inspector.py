"""Tests for runtime inspection and deadlock diagnostics."""

from datetime import UTC, datetime

from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.application.inspection import RuntimeInspector
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import TaskRunStatus, WorkflowRunStatus
from pyworkflowkit.domain.ids import TaskId, TaskRunId, WorkflowId, WorkflowRunId
from pyworkflowkit.domain.runtime import TaskRun, WorkflowRun

NOW = datetime(2026, 9, 26, 10, 0, tzinfo=UTC)


def _workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("inspect"),
        version="1",
        tasks=(
            TaskDefinition(task_id=TaskId("A"), handler_ref="handlers:a"),
            TaskDefinition(
                task_id=TaskId("B"),
                handler_ref="handlers:b",
                depends_on=(TaskId("A"),),
            ),
        ),
    )


def test_inspector_identifies_ready_and_blocked_tasks() -> None:
    store = MemoryMetadataStore()
    with store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=WorkflowRunId("run"),
                workflow_id=WorkflowId("inspect"),
                workflow_version="1",
                status=WorkflowRunStatus.RUNNING,
                created_at=NOW,
                started_at=NOW,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=TaskRunId("run-A"),
                run_id=WorkflowRunId("run"),
                task_id=TaskId("A"),
                status=TaskRunStatus.PENDING,
                created_at=NOW,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=TaskRunId("run-B"),
                run_id=WorkflowRunId("run"),
                task_id=TaskId("B"),
                status=TaskRunStatus.PENDING,
                created_at=NOW,
            )
        )
        uow.commit()

    inspection = RuntimeInspector(metadata_store=store).inspect(
        workflow=_workflow(),
        run_id=WorkflowRunId("run"),
    )

    assert inspection.ready_task_ids == ("A",)
    assert inspection.blocked_task_ids == ("B",)
    assert inspection.deadlocked is False


def test_inspector_reports_deadlock_when_no_nonterminal_task_is_ready() -> None:
    store = MemoryMetadataStore()
    with store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=WorkflowRunId("run"),
                workflow_id=WorkflowId("inspect"),
                workflow_version="1",
                status=WorkflowRunStatus.RUNNING,
                created_at=NOW,
                started_at=NOW,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=TaskRunId("run-A"),
                run_id=WorkflowRunId("run"),
                task_id=TaskId("A"),
                status=TaskRunStatus.FAILED,
                created_at=NOW,
                finished_at=NOW,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=TaskRunId("run-B"),
                run_id=WorkflowRunId("run"),
                task_id=TaskId("B"),
                status=TaskRunStatus.PENDING,
                created_at=NOW,
            )
        )
        uow.commit()

    inspection = RuntimeInspector(metadata_store=store).inspect(
        workflow=_workflow(),
        run_id=WorkflowRunId("run"),
    )

    assert inspection.ready_task_ids == ()
    assert inspection.blocked_task_ids == ("B",)
    assert inspection.deadlocked is True
    assert inspection.deadlock_reason is not None
