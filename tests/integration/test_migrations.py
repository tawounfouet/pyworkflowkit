"""Alembic migration acceptance tests for SQLite."""

from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

import pytest
from sqlalchemy import MetaData, Table, insert, inspect, text

from pyworkflowkit.adapters.metadata.sqlite import (
    SQLiteMetadataStore,
    SQLiteSettings,
    create_sqlite_engine,
)
from pyworkflowkit.domain.ids import ArtifactId, TaskRunId, WorkflowRunId
from pyworkflowkit.domain.values import ArtifactReference
from pyworkflowkit.errors import MigrationCompatibilityError
from pyworkflowkit.migrations import (
    MIGRATION_HEAD_REVISION,
    assert_database_revision_compatible,
    current_revision,
    upgrade_database,
)

HEAD_REVISION = MIGRATION_HEAD_REVISION

LEGACY_RUN_ID = "00000000-0000-0000-0000-000000000101"
LEGACY_TASK_RUN_ID = "00000000-0000-0000-0000-000000000102"
LEGACY_ATTEMPT_ID = "00000000-0000-0000-0000-000000000103"
LEGACY_EVENT_ID = "00000000-0000-0000-0000-000000000104"
EXPECTED_TABLES = {
    "alembic_version",
    "artifact_references",
    "external_run_refs",
    "runtime_events",
    "task_attempts",
    "task_output_checkpoints",
    "task_runs",
    "workflow_runs",
    "v2_external_run_refs",
    "v2_manifest_references",
    "v2_state_transitions",
    "v2_task_attempts",
    "v2_task_output_checkpoints",
    "v2_task_runs",
    "v2_workflow_runs",
}


def test_sqlite_fresh_upgrade_reaches_head(tmp_path: Path) -> None:
    database = tmp_path / "migration.sqlite3"
    engine = create_sqlite_engine(SQLiteSettings(path=database, wal=False))

    upgrade_database(engine)

    assert current_revision(engine) == HEAD_REVISION
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    task_attempt_columns = {column["name"] for column in inspector.get_columns("task_attempts")}
    assert "retry_eligible_at" in task_attempt_columns

    upgrade_database(engine)
    assert current_revision(engine) == HEAD_REVISION
    engine.dispose()


def test_migration_revisions_are_packaged() -> None:
    versions = files("pyworkflowkit.migrations.versions")
    assert versions.joinpath("0001_runtime_metadata.py").is_file()
    assert versions.joinpath("0002_task_output_checkpoints.py").is_file()
    assert versions.joinpath("0003_retry_eligible_at.py").is_file()
    assert versions.joinpath("0004_v2_runtime_metadata.py").is_file()
    assert versions.joinpath("0005_v2_task_output_checkpoints.py").is_file()


def _seed_sqlite_historical_data(engine, *, revision: str) -> None:  # type: ignore[no-untyped-def]
    metadata = MetaData()
    workflow_runs = Table("workflow_runs", metadata, autoload_with=engine)
    task_runs = Table("task_runs", metadata, autoload_with=engine)
    task_attempts = Table("task_attempts", metadata, autoload_with=engine)
    runtime_events = Table("runtime_events", metadata, autoload_with=engine)

    started_at = datetime(2026, 9, 26, 10, 0, tzinfo=UTC)
    finished_at = datetime(2026, 9, 26, 10, 1, tzinfo=UTC)

    with engine.begin() as connection:
        connection.execute(
            insert(workflow_runs),
            {
                "run_id": LEGACY_RUN_ID,
                "workflow_id": "legacy.workflow",
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
                "task_run_id": LEGACY_TASK_RUN_ID,
                "run_id": LEGACY_RUN_ID,
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
                "attempt_id": LEGACY_ATTEMPT_ID,
                "task_run_id": LEGACY_TASK_RUN_ID,
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
                "event_id": LEGACY_EVENT_ID,
                "event_type": "WORKFLOW_SUCCEEDED",
                "run_id": LEGACY_RUN_ID,
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
                autoload_with=engine,
            )
            connection.execute(
                insert(checkpoints),
                {
                    "task_run_id": LEGACY_TASK_RUN_ID,
                    "output_json": {"legacy": True, "origin": revision},
                },
            )


@pytest.mark.parametrize(
    "origin_revision",
    [
        "0001_runtime_metadata",
        "0002_task_output_checkpoints",
        "0003_retry_eligible_at",
    ],
)
def test_sqlite_historical_upgrade_preserves_data_and_accepts_current_writes(
    tmp_path: Path,
    origin_revision: str,
) -> None:
    database = tmp_path / f"{origin_revision}.sqlite3"
    engine = create_sqlite_engine(SQLiteSettings(path=database, wal=False))

    assert assert_database_revision_compatible(engine) is None
    upgrade_database(engine, origin_revision)
    assert current_revision(engine) == origin_revision

    _seed_sqlite_historical_data(engine, revision=origin_revision)
    upgrade_database(engine)

    assert current_revision(engine) == HEAD_REVISION

    with SQLiteMetadataStore(database, wal=False, create_schema=False) as store:
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


def test_upgrade_database_rejects_unknown_database_revision(tmp_path: Path) -> None:
    database = tmp_path / "future.sqlite3"
    engine = create_sqlite_engine(SQLiteSettings(path=database, wal=False))

    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)")
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('9999_future_revision')")
        )

    with pytest.raises(MigrationCompatibilityError, match="9999_future_revision"):
        upgrade_database(engine)

    engine.dispose()


def test_upgrade_database_rejects_unknown_target_revision(tmp_path: Path) -> None:
    database = tmp_path / "unknown-target.sqlite3"
    engine = create_sqlite_engine(SQLiteSettings(path=database, wal=False))

    with pytest.raises(MigrationCompatibilityError, match="9999_unknown_target"):
        upgrade_database(engine, "9999_unknown_target")

    engine.dispose()
