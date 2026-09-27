"""Alembic migration acceptance tests for PostgreSQL."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import MetaData, Table, insert, inspect, text

from pyworkflowkit.adapters.metadata.postgres import (
    PostgresMetadataStore,
    PostgresSettings,
    create_postgres_engine,
)
from pyworkflowkit.domain.ids import ArtifactId, TaskRunId, WorkflowRunId
from pyworkflowkit.domain.values import ArtifactReference
from pyworkflowkit.migrations import MIGRATION_HEAD_REVISION, current_revision, upgrade_database

POSTGRES_DSN = os.environ.get("PYWORKFLOWKIT_TEST_POSTGRES_DSN")
HEAD_REVISION = MIGRATION_HEAD_REVISION

LEGACY_RUN_ID = "00000000-0000-0000-0000-000000000201"
LEGACY_TASK_RUN_ID = "00000000-0000-0000-0000-000000000202"
LEGACY_ATTEMPT_ID = "00000000-0000-0000-0000-000000000203"
LEGACY_EVENT_ID = "00000000-0000-0000-0000-000000000204"
EXPECTED_TABLES = {
    "alembic_version",
    "artifact_references",
    "external_run_refs",
    "runtime_events",
    "task_attempts",
    "task_output_checkpoints",
    "task_runs",
    "workflow_runs",
}

pytestmark = pytest.mark.skipif(
    POSTGRES_DSN is None,
    reason="PYWORKFLOWKIT_TEST_POSTGRES_DSN is not configured",
)


def _dsn() -> str:
    assert POSTGRES_DSN is not None
    return POSTGRES_DSN


def test_postgres_fresh_upgrade_reaches_head() -> None:
    engine = create_postgres_engine(PostgresSettings(dsn=_dsn()))

    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS pyworkflowkit CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))

    upgrade_database(engine)

    inspector = inspect(engine)
    assert current_revision(engine) == HEAD_REVISION
    assert set(inspector.get_table_names(schema="pyworkflowkit")) == EXPECTED_TABLES

    columns = {
        column["name"]: str(column["type"]).upper()
        for column in inspector.get_columns("workflow_runs", schema="pyworkflowkit")
    }
    assert columns["run_id"] == "UUID"
    assert "TIMESTAMP" in columns["created_at"]
    assert columns["parameters_json"] == "JSONB"

    task_attempt_columns = {
        column["name"]: str(column["type"]).upper()
        for column in inspector.get_columns("task_attempts", schema="pyworkflowkit")
    }
    assert "retry_eligible_at" in task_attempt_columns
    assert "TIMESTAMP" in task_attempt_columns["retry_eligible_at"]

    upgrade_database(engine)
    assert current_revision(engine) == HEAD_REVISION
    engine.dispose()


def _reset_postgres_schema(engine) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS pyworkflowkit CASCADE"))
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


def _seed_postgres_historical_data(engine, *, revision: str) -> None:  # type: ignore[no-untyped-def]
    metadata = MetaData()
    workflow_runs = Table(
        "workflow_runs",
        metadata,
        schema="pyworkflowkit",
        autoload_with=engine,
    )
    task_runs = Table(
        "task_runs",
        metadata,
        schema="pyworkflowkit",
        autoload_with=engine,
    )
    task_attempts = Table(
        "task_attempts",
        metadata,
        schema="pyworkflowkit",
        autoload_with=engine,
    )
    runtime_events = Table(
        "runtime_events",
        metadata,
        schema="pyworkflowkit",
        autoload_with=engine,
    )

    started_at = datetime(2026, 9, 26, 11, 0, tzinfo=UTC)
    finished_at = datetime(2026, 9, 26, 11, 1, tzinfo=UTC)

    with engine.begin() as connection:
        connection.execute(
            insert(workflow_runs),
            {
                "run_id": UUID(LEGACY_RUN_ID),
                "workflow_id": "legacy.postgres",
                "workflow_version": "1",
                "status": "SUCCEEDED",
                "parameters_json": {"origin": revision},
                "created_at": started_at,
                "started_at": started_at,
                "finished_at": finished_at,
            },
        )
        connection.execute(
            insert(task_runs),
            {
                "task_run_id": UUID(LEGACY_TASK_RUN_ID),
                "run_id": UUID(LEGACY_RUN_ID),
                "task_id": "legacy-task",
                "status": "SUCCEEDED",
                "skip_reason": None,
                "created_at": started_at,
                "started_at": started_at,
                "finished_at": finished_at,
            },
        )
        connection.execute(
            insert(task_attempts),
            {
                "attempt_id": UUID(LEGACY_ATTEMPT_ID),
                "task_run_id": UUID(LEGACY_TASK_RUN_ID),
                "attempt_number": 1,
                "status": "SUCCEEDED",
                "started_at": started_at,
                "finished_at": finished_at,
                "error_type": None,
                "error_message": None,
                "error_category": None,
                "error_metadata_json": {},
            },
        )
        connection.execute(
            insert(runtime_events),
            {
                "event_id": UUID(LEGACY_EVENT_ID),
                "event_type": "WORKFLOW_SUCCEEDED",
                "run_id": UUID(LEGACY_RUN_ID),
                "occurred_at": finished_at,
                "event_sequence": 1,
                "task_run_id": None,
                "task_id": None,
                "attempt_number": None,
                "payload_json": {"origin": revision},
            },
        )

        if revision == "0002_task_output_checkpoints":
            checkpoints = Table(
                "task_output_checkpoints",
                MetaData(),
                schema="pyworkflowkit",
                autoload_with=engine,
            )
            connection.execute(
                insert(checkpoints),
                {
                    "task_run_id": UUID(LEGACY_TASK_RUN_ID),
                    "output_json": {"legacy": True, "origin": revision},
                },
            )


@pytest.mark.parametrize(
    "origin_revision",
    [
        "0001_runtime_metadata",
        "0002_task_output_checkpoints",
    ],
)
def test_postgres_historical_upgrade_preserves_data_and_accepts_current_writes(
    origin_revision: str,
) -> None:
    engine = create_postgres_engine(PostgresSettings(dsn=_dsn()))
    _reset_postgres_schema(engine)

    upgrade_database(engine, origin_revision)
    assert current_revision(engine) == origin_revision

    _seed_postgres_historical_data(engine, revision=origin_revision)
    upgrade_database(engine)

    assert current_revision(engine) == HEAD_REVISION

    with PostgresMetadataStore(_dsn(), create_schema=False) as store:
        run = store.get_workflow_run(WorkflowRunId(LEGACY_RUN_ID))
        task_run = store.list_task_runs(run.run_id)[0]
        attempt = store.list_task_attempts(task_run.task_run_id)[0]
        events = store.list_events(run.run_id)

        assert run.parameters["origin"] == origin_revision
        assert str(task_run.task_run_id) == LEGACY_TASK_RUN_ID
        assert attempt.retry_eligible_at is None
        assert events[0].payload["origin"] == origin_revision

        if origin_revision == "0002_task_output_checkpoints":
            assert store.get_task_output_checkpoint(TaskRunId(LEGACY_TASK_RUN_ID)) == {
                "legacy": True,
                "origin": origin_revision,
            }

        artifact = ArtifactReference(
            artifact_id=ArtifactId(f"post-upgrade-{origin_revision}"),
            name="post-upgrade",
            uri="memory://post-upgrade",
            metadata={"origin": origin_revision},
        )
        with store.unit_of_work() as uow:
            uow.add_artifact(
                task_run_id=TaskRunId(LEGACY_TASK_RUN_ID),
                artifact=artifact,
            )
            uow.commit()

        assert store.list_artifacts(TaskRunId(LEGACY_TASK_RUN_ID)) == (artifact,)

    engine.dispose()
