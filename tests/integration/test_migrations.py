"""Alembic migration acceptance tests for SQLite."""

from importlib.resources import files
from pathlib import Path

from sqlalchemy import inspect

from pyworkflowkit.adapters.metadata.sqlite import SQLiteSettings, create_sqlite_engine
from pyworkflowkit.migrations import current_revision, upgrade_database

HEAD_REVISION = "0001_runtime_metadata"
EXPECTED_TABLES = {
    "alembic_version",
    "artifact_references",
    "external_run_refs",
    "runtime_events",
    "task_attempts",
    "task_runs",
    "workflow_runs",
}


def test_sqlite_fresh_upgrade_reaches_head(tmp_path: Path) -> None:
    database = tmp_path / "migration.sqlite3"
    engine = create_sqlite_engine(SQLiteSettings(path=database, wal=False))

    upgrade_database(engine)

    assert current_revision(engine) == HEAD_REVISION
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES

    upgrade_database(engine)
    assert current_revision(engine) == HEAD_REVISION
    engine.dispose()


def test_baseline_revision_is_packaged() -> None:
    revision = files("pyworkflowkit.migrations.versions").joinpath("0001_runtime_metadata.py")
    assert revision.is_file()
