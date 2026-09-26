"""Durable SQLite persistence acceptance tests."""

from pathlib import Path

from sqlalchemy import text

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.metadata.sqlite import SQLiteMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import RuntimeEventType, WorkflowRunStatus
from pyworkflowkit.domain.ids import TaskId, WorkflowId


def _run_one_task(path: Path) -> str:
    handlers = HandlerRegistry()
    handlers.register("handlers:hello", lambda: {"message": "hello"})

    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("sqlite.restart"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("hello"),
                handler_ref="handlers:hello",
            ),
        ),
    )

    with SQLiteMetadataStore(path) as store:
        runner = Runner(
            metadata_store=store,
            handler_registry=handlers,
            executor=LocalExecutor(),
            clock=SystemClock(),
            id_factory=UuidRuntimeIdFactory(),
            sleeper=SystemSleeper(),
        )
        run = runner.run(workflow)
        return str(run.run_id)


def test_sqlite_run_survives_store_restart(tmp_path: Path) -> None:
    database = tmp_path / "pyworkflow.sqlite3"
    run_id = _run_one_task(database)

    with SQLiteMetadataStore(database) as reopened:
        run = reopened.get_workflow_run(run_id)
        task_runs = reopened.list_task_runs(run.run_id)
        events = reopened.list_events(run.run_id)

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert len(task_runs) == 1
    assert [event.event_type for event in events] == [
        RuntimeEventType.WORKFLOW_STARTED,
        RuntimeEventType.TASK_READY,
        RuntimeEventType.TASK_STARTED,
        RuntimeEventType.TASK_SUCCEEDED,
        RuntimeEventType.WORKFLOW_SUCCEEDED,
    ]


def test_sqlite_connection_pragmas_are_configured(tmp_path: Path) -> None:
    database = tmp_path / "pragmas.sqlite3"

    with (
        SQLiteMetadataStore(database, busy_timeout_ms=4_321, wal=True) as store,
        store.engine.connect() as connection,
    ):
        foreign_keys = connection.execute(text("PRAGMA foreign_keys")).scalar_one()
        busy_timeout = connection.execute(text("PRAGMA busy_timeout")).scalar_one()
        journal_mode = connection.execute(text("PRAGMA journal_mode")).scalar_one()

    assert foreign_keys == 1
    assert busy_timeout == 4_321
    assert str(journal_mode).lower() == "wal"


def test_sqlite_store_creates_parent_directory(tmp_path: Path) -> None:
    database = tmp_path / "nested" / "state" / "pyworkflow.sqlite3"

    with SQLiteMetadataStore(database):
        pass

    assert database.is_file()
