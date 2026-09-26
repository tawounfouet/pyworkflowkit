"""Alembic migration acceptance tests for SQLite."""

from importlib.resources import files
from pathlib import Path

from sqlalchemy import inspect

from pyworkflowkit.adapters.metadata.sqlite import SQLiteSettings, create_sqlite_engine
from pyworkflowkit.migrations import current_revision, upgrade_database

HEAD_REVISION = "0003_retry_eligible_at"
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


def test_sqlite_fresh_upgrade_reaches_head(tmp_path: Path) -> None:
    database = tmp_path / "migration.sqlite3"
    engine = create_sqlite_engine(SQLiteSettings(path=database, wal=False))

    upgrade_database(engine)

    assert current_revision(engine) == HEAD_REVISION
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == EXPECTED_TABLES
    task_attempt_columns = {
        column["name"] for column in inspector.get_columns("task_attempts")
    }
    assert "retry_eligible_at" in task_attempt_columns

    upgrade_database(engine)
    assert current_revision(engine) == HEAD_REVISION
    engine.dispose()


def test_migration_revisions_are_packaged() -> None:
    versions = files("pyworkflowkit.migrations.versions")
    assert versions.joinpath("0001_runtime_metadata.py").is_file()
    assert versions.joinpath("0002_task_output_checkpoints.py").is_file()
    assert versions.joinpath("0003_retry_eligible_at.py").is_file()
