"""Durable retry eligibility for non-blocking retry.

Revision ID: 0003_retry_eligible_at
Revises: 0002_task_output_checkpoints
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from pyworkflowkit.adapters.metadata.sqlalchemy.base import UTCDateTime

revision: str = "0003_retry_eligible_at"
down_revision: str | None = "0002_task_output_checkpoints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _schema() -> str | None:
    return "pyworkflowkit" if op.get_bind().dialect.name == "postgresql" else None


def upgrade() -> None:
    op.add_column(
        "task_attempts",
        sa.Column("retry_eligible_at", UTCDateTime(), nullable=True),
        schema=_schema(),
    )


def downgrade() -> None:
    op.drop_column(
        "task_attempts",
        "retry_eligible_at",
        schema=_schema(),
    )
