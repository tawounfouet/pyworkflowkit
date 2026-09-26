"""Initial runtime metadata schema.

Revision ID: 0001_runtime_metadata
Revises:
Create Date: 2026-09-26
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from pyworkflowkit.adapters.metadata.sqlalchemy.base import RuntimeIdType, UTCDateTime

revision: str = "0001_runtime_metadata"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _schema() -> str | None:
    return "pyworkflowkit" if op.get_bind().dialect.name == "postgresql" else None


def _json_type() -> sa.types.TypeEngine[Any]:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.JSONB()
    return sa.JSON()


def _fk_table(table: str) -> str:
    schema = _schema()
    return f"{schema}.{table}" if schema else table


def upgrade() -> None:
    schema = _schema()

    op.create_table(
        "workflow_runs",
        sa.Column("run_id", RuntimeIdType(), nullable=False),
        sa.Column("workflow_id", sa.Text(), nullable=False),
        sa.Column("workflow_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("parameters_json", _json_type(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=True),
        sa.Column("started_at", UTCDateTime(), nullable=True),
        sa.Column("finished_at", UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_workflow_runs_status_valid",
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_workflow_runs"),
        schema=schema,
    )
    op.create_index(
        "ix_workflow_runs_workflow",
        "workflow_runs",
        ["workflow_id", "workflow_version"],
        schema=schema,
    )

    op.create_table(
        "task_runs",
        sa.Column("task_run_id", RuntimeIdType(), nullable=False),
        sa.Column("run_id", RuntimeIdType(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=True),
        sa.Column("started_at", UTCDateTime(), nullable=True),
        sa.Column("finished_at", UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','READY','RUNNING','SUCCEEDED','FAILED','SKIPPED','CANCELLED')",
            name="ck_task_runs_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            [f"{_fk_table('workflow_runs')}.run_id"],
            name="fk_task_runs_workflow_run",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("task_run_id", name="pk_task_runs"),
        sa.UniqueConstraint("run_id", "task_id", name="uq_task_runs_run_task"),
        schema=schema,
    )
    op.create_index("ix_task_runs_run", "task_runs", ["run_id"], schema=schema)

    op.create_table(
        "task_attempts",
        sa.Column("attempt_id", RuntimeIdType(), nullable=False),
        sa.Column("task_run_id", RuntimeIdType(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", UTCDateTime(), nullable=True),
        sa.Column("finished_at", UTCDateTime(), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_category", sa.Text(), nullable=True),
        sa.Column("error_metadata_json", _json_type(), nullable=False),
        sa.CheckConstraint("attempt_number >= 1", name="ck_task_attempts_number_positive"),
        sa.CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="ck_task_attempts_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["task_run_id"],
            [f"{_fk_table('task_runs')}.task_run_id"],
            name="fk_task_attempts_task_run",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_task_attempts"),
        sa.UniqueConstraint("task_run_id", "attempt_number", name="uq_task_attempts_number"),
        schema=schema,
    )
    op.create_index(
        "ix_task_attempts_task_run",
        "task_attempts",
        ["task_run_id", "attempt_number"],
        schema=schema,
    )
    if op.get_bind().dialect.name == "postgresql":
        op.create_index(
            "uq_task_attempts_one_running",
            "task_attempts",
            ["task_run_id"],
            unique=True,
            schema=schema,
            postgresql_where=sa.text("status = 'RUNNING'"),
        )

    op.create_table(
        "runtime_events",
        sa.Column("event_id", RuntimeIdType(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("run_id", RuntimeIdType(), nullable=False),
        sa.Column("occurred_at", UTCDateTime(), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=True),
        sa.Column("task_run_id", RuntimeIdType(), nullable=True),
        sa.Column("task_id", sa.Text(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=True),
        sa.Column("payload_json", _json_type(), nullable=False),
        sa.CheckConstraint(
            """
            event_type IN (
              'WORKFLOW_STARTED','WORKFLOW_SUCCEEDED','WORKFLOW_FAILED',
              'WORKFLOW_CANCELLED','TASK_READY','TASK_STARTED','TASK_RETRYING',
              'TASK_SUCCEEDED','TASK_FAILED','TASK_SKIPPED'
            )
            """,
            name="ck_runtime_events_event_type_valid",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            [f"{_fk_table('workflow_runs')}.run_id"],
            name="fk_runtime_events_run",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_run_id"],
            [f"{_fk_table('task_runs')}.task_run_id"],
            name="fk_runtime_events_task_run",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_runtime_events"),
        sa.UniqueConstraint("run_id", "event_sequence", name="uq_runtime_events_sequence"),
        schema=schema,
    )
    op.create_index(
        "ix_runtime_events_run",
        "runtime_events",
        ["run_id", "event_sequence"],
        schema=schema,
    )

    op.create_table(
        "artifact_references",
        sa.Column("artifact_id", sa.Text(), nullable=False),
        sa.Column("task_run_id", RuntimeIdType(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=True),
        sa.Column("checksum", sa.Text(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=False),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="ck_artifact_references_size_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["task_run_id"],
            [f"{_fk_table('task_runs')}.task_run_id"],
            name="fk_artifact_references_task_run",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("artifact_id", name="pk_artifact_references"),
        schema=schema,
    )
    op.create_index(
        "ix_artifact_references_task",
        "artifact_references",
        ["task_run_id"],
        schema=schema,
    )

    op.create_table(
        "external_run_refs",
        sa.Column("external_ref_id", sa.Text(), nullable=False),
        sa.Column("task_run_id", RuntimeIdType(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("external_run_id", sa.Text(), nullable=False),
        sa.Column("uri", sa.Text(), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_run_id"],
            [f"{_fk_table('task_runs')}.task_run_id"],
            name="fk_external_run_refs_task_run",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("external_ref_id", name="pk_external_run_refs"),
        sa.UniqueConstraint(
            "task_run_id",
            "provider",
            "external_run_id",
            name="uq_external_run_refs_identity",
        ),
        schema=schema,
    )
    op.create_index(
        "ix_external_run_refs_task",
        "external_run_refs",
        ["task_run_id"],
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema()

    op.drop_index("ix_external_run_refs_task", table_name="external_run_refs", schema=schema)
    op.drop_table("external_run_refs", schema=schema)
    op.drop_index("ix_artifact_references_task", table_name="artifact_references", schema=schema)
    op.drop_table("artifact_references", schema=schema)
    op.drop_index("ix_runtime_events_run", table_name="runtime_events", schema=schema)
    op.drop_table("runtime_events", schema=schema)

    if op.get_bind().dialect.name == "postgresql":
        op.drop_index(
            "uq_task_attempts_one_running",
            table_name="task_attempts",
            schema=schema,
        )
    op.drop_index("ix_task_attempts_task_run", table_name="task_attempts", schema=schema)
    op.drop_table("task_attempts", schema=schema)
    op.drop_index("ix_task_runs_run", table_name="task_runs", schema=schema)
    op.drop_table("task_runs", schema=schema)
    op.drop_index("ix_workflow_runs_workflow", table_name="workflow_runs", schema=schema)
    op.drop_table("workflow_runs", schema=schema)
