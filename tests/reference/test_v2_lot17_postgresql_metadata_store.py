"""LOT-17 reference acceptance for canonical V2 PostgreSQL persistence."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.persistence as persistence
from pyworkflowkit.migrations import MIGRATION_HEAD_REVISION, MIGRATION_HISTORY
from pyworkflowkit.persistence import (
    PostgreSQLMetadataStore,
    PostgreSQLSettings,
    V2_METADATA_STORE_METHODS,
)


def test_lot17_public_surface_exposes_postgresql_without_touching_root() -> None:
    assert "PostgreSQLMetadataStore" in persistence.__all__
    assert "PostgreSQLSettings" in persistence.__all__
    assert "create_postgresql_engine" in persistence.__all__

    assert "PostgreSQLMetadataStore" not in pyworkflowkit.__all__
    assert "PostgreSQLSettings" not in pyworkflowkit.__all__


def test_lot17_postgresql_store_implements_complete_v2_method_surface() -> None:
    missing = [
        method
        for method in V2_METADATA_STORE_METHODS
        if not hasattr(PostgreSQLMetadataStore, method)
    ]

    assert missing == []


def test_lot17_reuses_existing_v2_migration_head_without_fake_revision() -> None:
    assert MIGRATION_HEAD_REVISION == "0005_v2_task_output_checkpoints"
    assert MIGRATION_HISTORY[-2:] == (
        "0004_v2_runtime_metadata",
        "0005_v2_task_output_checkpoints",
    )
    assert not any("lot17" in revision.lower() for revision in MIGRATION_HISTORY)


def test_lot17_settings_are_constructible_without_connecting() -> None:
    settings = PostgreSQLSettings(
        "postgresql+psycopg://user:password@localhost/pyworkflowkit",
    )

    assert settings.pool_size == 5
    assert settings.max_overflow == 10
    assert settings.application_name == "pyworkflowkit-v2"
