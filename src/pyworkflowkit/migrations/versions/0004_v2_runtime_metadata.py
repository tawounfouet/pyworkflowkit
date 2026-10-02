"""Canonical V2 durable runtime metadata.

Revision ID: 0004_v2_runtime_metadata
Revises: 0003_retry_eligible_at
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from pyworkflowkit.persistence._sqlalchemy.base import UTCDateTime

revision: str = "0004_v2_runtime_metadata"
down_revision: str | None = "0003_retry_eligible_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _schema() -> str | None:
    return "pyworkflowkit" if op.get_bind().dialect.name == "postgresql" else None


def _reference(table: str, column: str) -> str:
    schema = _schema()
    prefix = f"{schema}." if schema is not None else ""
    return f"{prefix}{table}.{column}"


def upgrade() -> None:
    schema = _schema()

    op.create_table(
        "v2_workflow_runs",
        sa.Column("run_id", sa.Text(), primary_key=True),
        sa.Column("workflow_name", sa.Text(), nullable=False),
        sa.Column("workflow_version", sa.Text(), nullable=False),
        sa.Column("definition_fingerprint", sa.Text(), nullable=False),
        sa.Column("plan_fingerprint", sa.Text(), nullable=False),
        sa.Column("correlation_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("started_at", UTCDateTime(), nullable=True),
        sa.Column("ended_at", UTCDateTime(), nullable=True),
        sa.Column("failure_json", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLATION_REQUESTED',"
            "'CANCELLED','TIMED_OUT','UNKNOWN_OUTCOME')",
            name="ck_v2_workflow_runs_status_valid",
        ),
        schema=schema,
    )
    op.create_index(
        "ix_v2_workflow_runs_status",
        "v2_workflow_runs",
        ["status"],
        schema=schema,
    )

    op.create_table(
        "v2_task_runs",
        sa.Column("task_run_id", sa.Text(), primary_key=True),
        sa.Column(
            "workflow_run_id",
            sa.Text(),
            sa.ForeignKey(
                _reference("v2_workflow_runs", "run_id"),
                onupdate="RESTRICT",
                ondelete="CASCADE",
                name="fk_v2_task_runs_workflow_run",
            ),
            nullable=False,
        ),
        sa.Column("task_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("started_at", UTCDateTime(), nullable=True),
        sa.Column("ended_at", UTCDateTime(), nullable=True),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column("failure_json", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "status IN ('PENDING','READY','RUNNING','SUCCEEDED','FAILED','SKIPPED',"
            "'CANCELLED','TIMED_OUT','BLOCKED','UNKNOWN_OUTCOME')",
            name="ck_v2_task_runs_status_valid",
        ),
        schema=schema,
    )
    op.create_index(
        "ix_v2_task_runs_workflow",
        "v2_task_runs",
        ["workflow_run_id", "task_key"],
        schema=schema,
    )

    op.create_table(
        "v2_task_attempts",
        sa.Column("attempt_id", sa.Text(), primary_key=True),
        sa.Column(
            "task_run_id",
            sa.Text(),
            sa.ForeignKey(
                _reference("v2_task_runs", "task_run_id"),
                onupdate="RESTRICT",
                ondelete="CASCADE",
                name="fk_v2_task_attempts_task_run",
            ),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("started_at", UTCDateTime(), nullable=True),
        sa.Column("ended_at", UTCDateTime(), nullable=True),
        sa.Column("failure_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint(
            "task_run_id",
            "attempt_number",
            name="uq_v2_task_attempts_number",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="ck_v2_task_attempts_number_positive",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','STARTING','RUNNING','SUCCEEDED','FAILED','TIMED_OUT',"
            "'CANCELLATION_REQUESTED','CANCELLED','CANCELLATION_UNCONFIRMED',"
            "'UNKNOWN_OUTCOME','REQUIRES_RECONCILIATION')",
            name="ck_v2_task_attempts_status_valid",
        ),
        schema=schema,
    )
    op.create_index(
        "ix_v2_task_attempts_task_run",
        "v2_task_attempts",
        ["task_run_id", "attempt_number"],
        schema=schema,
    )

    op.create_table(
        "v2_external_run_refs",
        sa.Column("external_ref_pk", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "attempt_id",
            sa.Text(),
            sa.ForeignKey(
                _reference("v2_task_attempts", "attempt_id"),
                onupdate="RESTRICT",
                ondelete="CASCADE",
                name="fk_v2_external_run_refs_attempt",
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("external_run_id", sa.Text(), nullable=False),
        sa.Column("status_hint", sa.Text(), nullable=True),
        sa.Column("status_locator", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column("causation_id", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("namespace", sa.Text(), nullable=False),
        sa.Column("contract_version", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "attempt_id",
            "provider",
            "kind",
            "external_run_id",
            name="uq_v2_external_run_refs_identity",
        ),
        schema=schema,
    )
    op.create_index(
        "ix_v2_external_run_refs_attempt",
        "v2_external_run_refs",
        ["attempt_id"],
        schema=schema,
    )

    op.create_table(
        "v2_state_transitions",
        sa.Column("sequence", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("occurred_at", UTCDateTime(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('workflow_run','task_run','task_attempt')",
            name="ck_v2_state_transitions_entity_type_valid",
        ),
        schema=schema,
    )
    op.create_index(
        "ix_v2_state_transitions_entity",
        "v2_state_transitions",
        ["entity_type", "entity_id", "sequence"],
        schema=schema,
    )

    op.create_table(
        "v2_manifest_references",
        sa.Column(
            "workflow_run_id",
            sa.Text(),
            sa.ForeignKey(
                _reference("v2_workflow_runs", "run_id"),
                onupdate="RESTRICT",
                ondelete="CASCADE",
                name="fk_v2_manifest_references_workflow_run",
            ),
            primary_key=True,
        ),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("digest", sa.Text(), nullable=True),
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema()
    op.drop_table("v2_manifest_references", schema=schema)
    op.drop_index(
        "ix_v2_state_transitions_entity",
        table_name="v2_state_transitions",
        schema=schema,
    )
    op.drop_table("v2_state_transitions", schema=schema)
    op.drop_index(
        "ix_v2_external_run_refs_attempt",
        table_name="v2_external_run_refs",
        schema=schema,
    )
    op.drop_table("v2_external_run_refs", schema=schema)
    op.drop_index(
        "ix_v2_task_attempts_task_run",
        table_name="v2_task_attempts",
        schema=schema,
    )
    op.drop_table("v2_task_attempts", schema=schema)
    op.drop_index(
        "ix_v2_task_runs_workflow",
        table_name="v2_task_runs",
        schema=schema,
    )
    op.drop_table("v2_task_runs", schema=schema)
    op.drop_index(
        "ix_v2_workflow_runs_status",
        table_name="v2_workflow_runs",
        schema=schema,
    )
    op.drop_table("v2_workflow_runs", schema=schema)
