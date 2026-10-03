"""Canonical V2 durable task-output evidence.

Revision ID: 0005_v2_task_output_checkpoints
Revises: 0004_v2_runtime_metadata
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from pyworkflowkit.persistence._sqlalchemy.base import UTCDateTime

revision: str = "0005_v2_task_output_checkpoints"
down_revision: str | None = "0004_v2_runtime_metadata"
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
        "v2_task_output_checkpoints",
        sa.Column(
            "task_run_id",
            sa.Text(),
            sa.ForeignKey(
                _reference("v2_task_runs", "task_run_id"),
                onupdate="RESTRICT",
                ondelete="CASCADE",
                name="fk_v2_task_output_checkpoints_task_run",
            ),
            primary_key=True,
        ),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("recorded_at", UTCDateTime(), nullable=False),
        sa.Column("digest", sa.Text(), nullable=False),
        schema=schema,
    )


def downgrade() -> None:
    op.drop_table("v2_task_output_checkpoints", schema=_schema())
