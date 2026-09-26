"""Common contract tests for MetadataStore implementations."""

from datetime import UTC, datetime

import pytest

from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.domain.enums import RuntimeEventType, TaskAttemptStatus, TaskRunStatus
from pyworkflowkit.domain.ids import (
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.errors import MetadataNotFoundError
from pyworkflowkit.ports.metadata_store import MetadataStore

NOW = datetime(2026, 9, 25, 18, 45, tzinfo=UTC)


@pytest.fixture
def store() -> MetadataStore:
    return MemoryMetadataStore()


def make_run() -> WorkflowRun:
    return WorkflowRun(
        run_id=WorkflowRunId("run"),
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
        created_at=NOW,
    )


def make_task_run() -> TaskRun:
    return TaskRun(
        task_run_id=TaskRunId("task-run"),
        run_id=WorkflowRunId("run"),
        task_id=TaskId("task"),
        created_at=NOW,
    )


def test_contract_commit_makes_data_visible(store: MetadataStore) -> None:
    with store.unit_of_work() as uow:
        uow.add_workflow_run(make_run())
        uow.add_task_run(make_task_run())
        uow.commit()

    assert store.get_workflow_run(WorkflowRunId("run")).workflow_id == WorkflowId("workflow")
    assert tuple(run.run_id for run in store.list_workflow_runs()) == (WorkflowRunId("run"),)
    assert len(store.list_task_runs(WorkflowRunId("run"))) == 1


def test_contract_rollback_keeps_data_invisible(store: MetadataStore) -> None:
    with store.unit_of_work() as uow:
        uow.add_workflow_run(make_run())
        uow.rollback()

    with pytest.raises(MetadataNotFoundError):
        store.get_workflow_run(WorkflowRunId("run"))


def test_contract_saved_runtime_state_requires_explicit_commit(
    store: MetadataStore,
) -> None:
    with store.unit_of_work() as uow:
        uow.add_workflow_run(make_run())
        uow.add_task_run(make_task_run())
        uow.commit()

    loaded = store.get_task_run(TaskRunId("task-run"))
    loaded.status = TaskRunStatus.READY

    assert store.get_task_run(TaskRunId("task-run")).status is TaskRunStatus.PENDING

    with store.unit_of_work() as uow:
        uow.save_task_run(loaded)
        uow.commit()

    assert store.get_task_run(TaskRunId("task-run")).status is TaskRunStatus.READY


def test_contract_attempt_and_event_history_are_queryable(
    store: MetadataStore,
) -> None:
    with store.unit_of_work() as uow:
        uow.add_workflow_run(make_run())
        uow.add_task_run(make_task_run())
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("attempt"),
                task_run_id=TaskRunId("task-run"),
                attempt_number=1,
                started_at=NOW,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("event"),
                event_type=RuntimeEventType.TASK_STARTED,
                run_id=WorkflowRunId("run"),
                occurred_at=NOW,
                event_sequence=1,
                task_run_id=TaskRunId("task-run"),
                task_id=TaskId("task"),
                attempt_number=1,
            )
        )
        uow.commit()

    assert len(store.list_task_attempts(TaskRunId("task-run"))) == 1
    assert len(store.list_events(WorkflowRunId("run"))) == 1


def test_contract_task_attempt_can_be_updated(store: MetadataStore) -> None:
    with store.unit_of_work() as uow:
        uow.add_workflow_run(make_run())
        uow.add_task_run(make_task_run())
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("attempt"),
                task_run_id=TaskRunId("task-run"),
                attempt_number=1,
                started_at=NOW,
            )
        )
        uow.commit()

    updated = store.list_task_attempts(TaskRunId("task-run"))[0]
    updated.status = TaskAttemptStatus.SUCCEEDED
    updated.finished_at = NOW

    with store.unit_of_work() as uow:
        uow.save_task_attempt(updated)
        uow.commit()

    persisted = store.list_task_attempts(TaskRunId("task-run"))[0]
    assert persisted.status is TaskAttemptStatus.SUCCEEDED


def test_contract_task_output_checkpoint_round_trips_and_preserves_none(
    store: MetadataStore,
) -> None:
    with store.unit_of_work() as uow:
        uow.add_workflow_run(make_run())
        uow.add_task_run(make_task_run())
        uow.add_task_output_checkpoint(
            task_run_id=TaskRunId("task-run"),
            output={"count": 3, "items": ["a", "b"]},
        )
        uow.commit()

    assert store.get_task_output_checkpoint(TaskRunId("task-run")) == {
        "count": 3,
        "items": ["a", "b"],
    }

    with pytest.raises(MetadataNotFoundError):
        store.get_task_output_checkpoint(TaskRunId("missing"))


def test_contract_retry_eligibility_round_trips(
    store: MetadataStore,
) -> None:
    eligible_at = NOW.replace(minute=(NOW.minute + 1) % 60)
    with store.unit_of_work() as uow:
        uow.add_workflow_run(make_run())
        uow.add_task_run(make_task_run())
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("attempt-retry"),
                task_run_id=TaskRunId("task-run"),
                attempt_number=1,
                status=TaskAttemptStatus.FAILED,
                started_at=NOW,
                finished_at=NOW,
                error_type="RuntimeError",
                error_message="temporary",
                error_category="RuntimeError",
                retry_eligible_at=eligible_at,
            )
        )
        uow.commit()

    persisted = store.list_task_attempts(TaskRunId("task-run"))[0]
    assert persisted.retry_eligible_at == eligible_at
