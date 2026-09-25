"""Tests for the transactional in-memory metadata adapter."""

from datetime import UTC, datetime

import pytest

from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.domain.enums import RuntimeEventType, TaskRunStatus, WorkflowRunStatus
from pyworkflowkit.domain.ids import (
    ArtifactId,
    ExternalRunRefId,
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef
from pyworkflowkit.errors import (
    DuplicateMetadataError,
    MetadataNotFoundError,
    UnitOfWorkStateError,
)
from pyworkflowkit.ports.metadata_store import MetadataStore

NOW = datetime(2026, 9, 25, 18, 30, tzinfo=UTC)


def workflow_run() -> WorkflowRun:
    return WorkflowRun(
        run_id=WorkflowRunId("run-1"),
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
        parameters={"source": "input.csv"},
        created_at=NOW,
    )


def task_run(task_id: str = "fetch") -> TaskRun:
    return TaskRun(
        task_run_id=TaskRunId(f"task-run-{task_id}"),
        run_id=WorkflowRunId("run-1"),
        task_id=TaskId(task_id),
        created_at=NOW,
    )


def attempt(number: int = 1) -> TaskAttempt:
    return TaskAttempt(
        attempt_id=TaskAttemptId(f"attempt-{number}"),
        task_run_id=TaskRunId("task-run-fetch"),
        attempt_number=number,
        started_at=NOW,
    )


def seed_run_and_task(store: MemoryMetadataStore) -> None:
    with store.unit_of_work() as uow:
        uow.add_workflow_run(workflow_run())
        uow.add_task_run(task_run())
        uow.commit()


def test_memory_store_satisfies_metadata_store_protocol() -> None:
    assert isinstance(MemoryMetadataStore(), MetadataStore)


def test_commit_publishes_workflow_and_task_runs() -> None:
    store = MemoryMetadataStore()

    with store.unit_of_work() as uow:
        uow.add_workflow_run(workflow_run())
        uow.add_task_run(task_run())
        uow.commit()

    assert store.get_workflow_run(WorkflowRunId("run-1")).workflow_version == "1"
    assert tuple(run.task_id for run in store.list_task_runs(WorkflowRunId("run-1"))) == (
        TaskId("fetch"),
    )


def test_uncommitted_context_exit_rolls_back() -> None:
    store = MemoryMetadataStore()

    with store.unit_of_work() as uow:
        uow.add_workflow_run(workflow_run())

    with pytest.raises(MetadataNotFoundError):
        store.get_workflow_run(WorkflowRunId("run-1"))


def test_exception_exit_rolls_back() -> None:
    store = MemoryMetadataStore()

    with pytest.raises(RuntimeError, match="boom"):
        with store.unit_of_work() as uow:
            uow.add_workflow_run(workflow_run())
            raise RuntimeError("boom")

    with pytest.raises(MetadataNotFoundError):
        store.get_workflow_run(WorkflowRunId("run-1"))


def test_explicit_rollback_discards_changes() -> None:
    store = MemoryMetadataStore()

    with store.unit_of_work() as uow:
        uow.add_workflow_run(workflow_run())
        uow.rollback()

    with pytest.raises(MetadataNotFoundError):
        store.get_workflow_run(WorkflowRunId("run-1"))


def test_store_reads_are_detached_from_persisted_runtime_state() -> None:
    store = MemoryMetadataStore()
    seed_run_and_task(store)

    loaded = store.get_task_run(TaskRunId("task-run-fetch"))
    loaded.status = TaskRunStatus.READY

    reloaded = store.get_task_run(TaskRunId("task-run-fetch"))

    assert reloaded.status is TaskRunStatus.PENDING


def test_save_workflow_run_replaces_persisted_snapshot_only_after_commit() -> None:
    store = MemoryMetadataStore()
    seed_run_and_task(store)

    loaded = store.get_workflow_run(WorkflowRunId("run-1"))
    loaded.status = WorkflowRunStatus.RUNNING
    loaded.started_at = NOW

    with store.unit_of_work() as uow:
        uow.save_workflow_run(loaded)
        assert store.get_workflow_run(WorkflowRunId("run-1")).status is WorkflowRunStatus.PENDING
        uow.commit()

    assert store.get_workflow_run(WorkflowRunId("run-1")).status is WorkflowRunStatus.RUNNING


def test_save_task_run_requires_existing_identity() -> None:
    store = MemoryMetadataStore()

    with store.unit_of_work() as uow:
        with pytest.raises(MetadataNotFoundError, match="TaskRun"):
            uow.save_task_run(task_run())


def test_duplicate_workflow_run_is_rejected() -> None:
    store = MemoryMetadataStore()

    with store.unit_of_work() as uow:
        run = workflow_run()
        uow.add_workflow_run(run)
        with pytest.raises(DuplicateMetadataError, match="WorkflowRun"):
            uow.add_workflow_run(run)


def test_task_run_requires_parent_workflow_run() -> None:
    store = MemoryMetadataStore()

    with store.unit_of_work() as uow:
        with pytest.raises(MetadataNotFoundError, match="WorkflowRun"):
            uow.add_task_run(task_run())


def test_attempt_requires_parent_task_run() -> None:
    store = MemoryMetadataStore()

    with store.unit_of_work() as uow:
        with pytest.raises(MetadataNotFoundError, match="TaskRun"):
            uow.add_task_attempt(attempt())


def test_duplicate_attempt_number_per_task_run_is_rejected() -> None:
    store = MemoryMetadataStore()
    seed_run_and_task(store)

    first = attempt(1)
    duplicate_number = TaskAttempt(
        attempt_id=TaskAttemptId("another-id"),
        task_run_id=first.task_run_id,
        attempt_number=1,
        started_at=NOW,
    )

    with store.unit_of_work() as uow:
        uow.add_task_attempt(first)
        with pytest.raises(DuplicateMetadataError, match="TaskAttemptNumber"):
            uow.add_task_attempt(duplicate_number)


def test_attempts_are_returned_in_attempt_number_order() -> None:
    store = MemoryMetadataStore()
    seed_run_and_task(store)

    with store.unit_of_work() as uow:
        uow.add_task_attempt(attempt(2))
        uow.add_task_attempt(attempt(1))
        uow.commit()

    assert tuple(
        value.attempt_number
        for value in store.list_task_attempts(TaskRunId("task-run-fetch"))
    ) == (1, 2)


def test_events_require_parent_run_and_are_sorted_by_sequence() -> None:
    store = MemoryMetadataStore()
    seed_run_and_task(store)

    later = RuntimeEvent(
        event_id=RuntimeEventId("event-2"),
        event_type=RuntimeEventType.TASK_STARTED,
        run_id=WorkflowRunId("run-1"),
        occurred_at=NOW,
        event_sequence=2,
    )
    earlier = RuntimeEvent(
        event_id=RuntimeEventId("event-1"),
        event_type=RuntimeEventType.WORKFLOW_STARTED,
        run_id=WorkflowRunId("run-1"),
        occurred_at=NOW,
        event_sequence=1,
    )

    with store.unit_of_work() as uow:
        uow.add_event(later)
        uow.add_event(earlier)
        uow.commit()

    assert tuple(event.event_id for event in store.list_events(WorkflowRunId("run-1"))) == (
        RuntimeEventId("event-1"),
        RuntimeEventId("event-2"),
    )


def test_event_for_unknown_run_is_rejected() -> None:
    store = MemoryMetadataStore()
    event = RuntimeEvent(
        event_id=RuntimeEventId("event-1"),
        event_type=RuntimeEventType.WORKFLOW_STARTED,
        run_id=WorkflowRunId("missing"),
        occurred_at=NOW,
    )

    with store.unit_of_work() as uow:
        with pytest.raises(MetadataNotFoundError, match="WorkflowRun"):
            uow.add_event(event)


def test_artifact_and_external_ref_are_associated_with_task_run() -> None:
    store = MemoryMetadataStore()
    seed_run_and_task(store)

    artifact = ArtifactReference(
        artifact_id=ArtifactId("artifact-1"),
        name="report.csv",
        uri="file:///tmp/report.csv",
    )
    external_ref = ExternalRunRef(
        external_ref_id=ExternalRunRefId("external-1"),
        provider="pyingestkit",
        external_run_id="job-1",
    )

    with store.unit_of_work() as uow:
        uow.add_artifact(
            task_run_id=TaskRunId("task-run-fetch"),
            artifact=artifact,
        )
        uow.add_external_run_ref(
            task_run_id=TaskRunId("task-run-fetch"),
            external_ref=external_ref,
        )
        uow.commit()

    assert store.list_artifacts(TaskRunId("task-run-fetch")) == (artifact,)
    assert store.list_external_run_refs(TaskRunId("task-run-fetch")) == (external_ref,)


def test_artifact_requires_parent_task_run() -> None:
    store = MemoryMetadataStore()
    artifact = ArtifactReference(
        artifact_id=ArtifactId("artifact-1"),
        name="report.csv",
        uri="file:///tmp/report.csv",
    )

    with store.unit_of_work() as uow:
        with pytest.raises(MetadataNotFoundError, match="TaskRun"):
            uow.add_artifact(
                task_run_id=TaskRunId("missing"),
                artifact=artifact,
            )


def test_unit_of_work_must_be_entered_before_use() -> None:
    store = MemoryMetadataStore()
    uow = store.unit_of_work()

    with pytest.raises(UnitOfWorkStateError, match="entered"):
        uow.add_workflow_run(workflow_run())


def test_committed_unit_of_work_cannot_be_reused_without_reentering() -> None:
    store = MemoryMetadataStore()

    with store.unit_of_work() as uow:
        uow.add_workflow_run(workflow_run())
        uow.commit()

        with pytest.raises(UnitOfWorkStateError, match="entered"):
            uow.add_task_run(task_run())


def test_nested_enter_on_same_unit_of_work_is_rejected() -> None:
    store = MemoryMetadataStore()
    uow = store.unit_of_work()

    with uow:
        with pytest.raises(UnitOfWorkStateError, match="already active"):
            uow.__enter__()
