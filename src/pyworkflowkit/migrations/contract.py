"""Stable persistence and migration compatibility contract for PyWorkflowKit."""

from __future__ import annotations

PERSISTENCE_SCHEMA_CONTRACT_VERSION = "1"

MIGRATION_HISTORY: tuple[str, ...] = (
    "0001_runtime_metadata",
    "0002_task_output_checkpoints",
    "0003_retry_eligible_at",
)

MIGRATION_HEAD_REVISION = MIGRATION_HISTORY[-1]
SUPPORTED_UPGRADE_ORIGINS: frozenset[str] = frozenset(MIGRATION_HISTORY)


def is_supported_database_revision(revision: str | None) -> bool:
    """Return whether a database revision is safe for this package to upgrade."""

    return revision is None or revision in SUPPORTED_UPGRADE_ORIGINS


def is_supported_upgrade_target(revision: str) -> bool:
    """Return whether an explicit Alembic upgrade target is owned by this package."""

    return revision == "head" or revision in MIGRATION_HISTORY


__all__ = [
    "MIGRATION_HEAD_REVISION",
    "MIGRATION_HISTORY",
    "PERSISTENCE_SCHEMA_CONTRACT_VERSION",
    "SUPPORTED_UPGRADE_ORIGINS",
    "is_supported_database_revision",
    "is_supported_upgrade_target",
]
