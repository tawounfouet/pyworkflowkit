"""PostgreSQL persistence integration and contract tests."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.metadata.postgres import PostgresMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import WorkflowRunStatus
from pyworkflowkit.domain.ids import TaskId, TaskRunId, WorkflowId

POSTGRES_DSN = os.environ.get("PYWORKFLOWKIT_TEST_POSTGRES_DSN")


pytestmark = pytest.mark.skipif(
    POSTGRES_DSN is None,
    reason="PYWORKFLOWKIT_TEST_POSTGRES_DSN is not configured",
)


def _dsn() -> str:
    assert POSTGRES_DSN is not None
    return POSTGRES_DSN


def test_postgres_runtime_round_trip_and_native_types() -> None:
    handlers = HandlerRegistry()
    handlers.register("handlers:hello", lambda: {"message": "hello"})

    workflow = WorkflowDefinition(
        workflow_id=WorkflowId(f"postgres-{uuid4()}"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("hello"),
                handler_ref="handlers:hello",
            ),
        ),
    )

    with PostgresMetadataStore(_dsn()) as store:
        runner = Runner(
            metadata_store=store,
            handler_registry=handlers,
            executor=LocalExecutor(),
            clock=SystemClock(),
            id_factory=UuidRuntimeIdFactory(),
            sleeper=SystemSleeper(),
        )
        run = runner.run(workflow)
        persisted = store.get_workflow_run(run.run_id)
        task_runs = store.list_task_runs(run.run_id)

        with store.engine.connect() as connection:
            columns = {
                (row.table_name, row.column_name): row.data_type
                for row in connection.execute(
                    text(
                        """
                        SELECT table_name, column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = 'pyworkflowkit'
                          AND (
                            (
                              table_name = 'workflow_runs'
                              AND column_name IN ('run_id', 'created_at', 'parameters_json')
                            )
                            OR (table_name = 'task_runs' AND column_name = 'task_run_id')
                          )
                        """
                    )
                )
            }

    assert persisted.status is WorkflowRunStatus.SUCCEEDED
    assert len(task_runs) == 1
    assert columns[("workflow_runs", "run_id")] == "uuid"
    assert columns[("workflow_runs", "created_at")] == "timestamp with time zone"
    assert columns[("workflow_runs", "parameters_json")] == "jsonb"
    assert columns[("task_runs", "task_run_id")] == "uuid"


def test_postgres_partial_running_attempt_index_exists() -> None:
    with PostgresMetadataStore(_dsn()) as store, store.engine.connect() as connection:
        definition = connection.execute(
            text(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'pyworkflowkit'
                  AND indexname = 'uq_task_attempts_one_running'
                """
            )
        ).scalar_one()

    normalized = " ".join(str(definition).split()).upper()
    assert "UNIQUE INDEX" in normalized
    assert "WHERE" in normalized
    assert "STATUS" in normalized
    assert "RUNNING" in normalized


def test_postgres_unit_of_work_can_lock_task_run() -> None:
    handlers = HandlerRegistry()
    handlers.register("handlers:lock", lambda: None)
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId(f"postgres-lock-{uuid4()}"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("lock"),
                handler_ref="handlers:lock",
            ),
        ),
    )

    with PostgresMetadataStore(_dsn()) as store:
        runner = Runner(
            metadata_store=store,
            handler_registry=handlers,
            executor=LocalExecutor(),
            clock=SystemClock(),
            id_factory=UuidRuntimeIdFactory(),
            sleeper=SystemSleeper(),
        )
        run = runner.run(workflow)
        task_run = store.list_task_runs(run.run_id)[0]

        with store.unit_of_work() as uow:
            locked = uow.lock_task_run(TaskRunId(str(task_run.task_run_id)))
            uow.rollback()

    assert locked.task_run_id == task_run.task_run_id


def test_postgres_session_is_read_committed_and_utc() -> None:
    with PostgresMetadataStore(_dsn()) as store, store.engine.connect() as connection:
        isolation = connection.execute(text("SHOW transaction_isolation")).scalar_one()
        timezone = connection.execute(text("SHOW timezone")).scalar_one()
        app_name = connection.execute(text("SHOW application_name")).scalar_one()

    assert str(isolation).lower() == "read committed"
    assert str(timezone).upper() == "UTC"
    assert app_name == "pyworkflowkit"
