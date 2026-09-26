"""Durable task-output checkpoints for resume.

Revision ID: 0002_task_output_checkpoints
Revises: 0001_runtime_metadata
Create Date: 2026-09-26
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from pyworkflowkit.adapters.metadata.sqlalchemy.base import RuntimeIdType

revision: str = "0002_task_output_checkpoints"
down_revision: str | None = "0001_runtime_metadata"
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
        "task_output_checkpoints",
        sa.Column("task_run_id", RuntimeIdType(), nullable=False),
        sa.Column("output_json", _json_type(), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_run_id"],
            [f"{_fk_table('task_runs')}.task_run_id"],
            name="fk_task_output_checkpoints_task_run",
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("task_run_id", name="pk_task_output_checkpoints"),
        schema=schema,
    )


def downgrade() -> None:
    op.drop_table("task_output_checkpoints", schema=_schema())
