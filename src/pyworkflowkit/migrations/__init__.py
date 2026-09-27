"""Schema migration support for PyWorkflowKit durable metadata stores."""

from pyworkflowkit.migrations.contract import (
    MIGRATION_HEAD_REVISION,
    MIGRATION_HISTORY,
    PERSISTENCE_SCHEMA_CONTRACT_VERSION,
    SUPPORTED_UPGRADE_ORIGINS,
)
from pyworkflowkit.migrations.runner import (
    assert_database_revision_compatible,
    current_revision,
    upgrade_database,
)

__all__ = [
    "MIGRATION_HEAD_REVISION",
    "MIGRATION_HISTORY",
    "PERSISTENCE_SCHEMA_CONTRACT_VERSION",
    "SUPPORTED_UPGRADE_ORIGINS",
    "assert_database_revision_compatible",
    "current_revision",
    "upgrade_database",
]
