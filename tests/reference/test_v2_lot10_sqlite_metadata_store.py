"""LOT-10 reference acceptance for durable V2 SQLite persistence."""

from __future__ import annotations

from pathlib import Path

import pyworkflowkit
import pyworkflowkit.persistence as persistence
from pyworkflowkit.migrations import MIGRATION_HEAD_REVISION, MIGRATION_HISTORY
from pyworkflowkit.persistence import MetadataStore, SQLiteMetadataStore


def test_lot10_public_surface_exposes_canonical_sqlite_without_touching_root() -> None:
    assert "SQLiteMetadataStore" in persistence.__all__
    assert "SQLiteSettings" in persistence.__all__
    assert "SQLiteMetadataStore" not in pyworkflowkit.__all__


def test_lot10_migration_lineage_is_append_only() -> None:
    index = MIGRATION_HISTORY.index("0004_v2_runtime_metadata")
    assert MIGRATION_HISTORY[index - 1 : index + 1] == (
        "0003_retry_eligible_at",
        "0004_v2_runtime_metadata",
    )
    assert MIGRATION_HEAD_REVISION in MIGRATION_HISTORY


def test_lot10_sqlite_store_satisfies_v2_metadata_protocol(tmp_path: Path) -> None:
    with SQLiteMetadataStore(tmp_path / "lot10.sqlite3", wal=False) as store:
        assert isinstance(store, MetadataStore)
        metadata = store.metadata()

    assert metadata.durable is True
    assert metadata.schema_version == "0004_v2_runtime_metadata"
    assert metadata.supports_concurrent_writers is True
