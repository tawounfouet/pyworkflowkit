"""Alembic migration acceptance tests for PostgreSQL."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import inspect, text

from pyworkflowkit.adapters.metadata.postgres import PostgresSettings, create_postgres_engine
from pyworkflowkit.migrations import current_revision, upgrade_database

POSTGRES_DSN = os.environ.get("PYWORKFLOWKIT_TEST_POSTGRES_DSN")
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

    upgrade_database(engine)
    assert current_revision(engine) == HEAD_REVISION
    engine.dispose()
