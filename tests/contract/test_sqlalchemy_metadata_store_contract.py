"""Contract checks for the dialect-neutral SQLAlchemy MetadataStore foundation."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pyworkflowkit.adapters.metadata.sqlalchemy import (
    DB_SCHEMA,
    Base,
    SqlAlchemyMetadataStore,
)
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

NOW = datetime(2026, 9, 26, 8, 0, tzinfo=UTC)


@pytest.fixture
def store() -> MetadataStore:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {DB_SCHEMA: None}},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    return SqlAlchemyMetadataStore(session_factory)


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


def test_sqlalchemy_store_satisfies_metadata_store_protocol(store: MetadataStore) -> None:
    assert isinstance(store, MetadataStore)


def test_sqlalchemy_contract_commit_and_round_trip(store: MetadataStore) -> None:
    with store.unit_of_work() as uow:
        uow.add_workflow_run(make_run())
        uow.add_task_run(make_task_run())
        uow.commit()

    loaded = store.get_workflow_run(WorkflowRunId("run"))
    assert loaded.workflow_id == WorkflowId("workflow")
    assert loaded.created_at == NOW
    assert len(store.list_task_runs(WorkflowRunId("run"))) == 1


def test_sqlalchemy_contract_rollback_keeps_data_invisible(store: MetadataStore) -> None:
    with store.unit_of_work() as uow:
        uow.add_workflow_run(make_run())
        uow.rollback()

    with pytest.raises(MetadataNotFoundError):
        store.get_workflow_run(WorkflowRunId("run"))


def test_sqlalchemy_contract_attempt_event_and_update(store: MetadataStore) -> None:
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

    attempt = store.list_task_attempts(TaskRunId("task-run"))[0]
    attempt.status = TaskAttemptStatus.SUCCEEDED
    attempt.finished_at = NOW

    task_run = store.get_task_run(TaskRunId("task-run"))
    task_run.status = TaskRunStatus.SUCCEEDED
    task_run.started_at = NOW
    task_run.finished_at = NOW

    with store.unit_of_work() as uow:
        uow.save_task_attempt(attempt)
        uow.save_task_run(task_run)
        uow.commit()

    assert store.list_task_attempts(TaskRunId("task-run"))[0].status is TaskAttemptStatus.SUCCEEDED
    assert store.list_events(WorkflowRunId("run"))[0].event_type is RuntimeEventType.TASK_STARTED
