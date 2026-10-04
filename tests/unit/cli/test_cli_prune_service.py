"""Unit tests for PruneService store resolution and orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pyworkflowkit.cli.services.prune_service import PruneService
from pyworkflowkit.persistence import InMemoryMetadataStore, SQLiteMetadataStore
from pyworkflowkit.persistence.retention import RetentionPolicy


def test_prune_service_with_injected_store() -> None:
    store = InMemoryMetadataStore()
    service = PruneService(store=store)

    policy = RetentionPolicy(retention_days=10)
    report = service.prune(policy, dry_run=True)

    assert report.dry_run is True
    assert report.scanned_workflows == 0
    assert report.eligible_runs_to_prune == 0


def test_prune_service_resolve_explicit_db(tmp_path: Path) -> None:
    service = PruneService()
    db_path = tmp_path / "explicit.sqlite3"
    resolved = service.resolve_store(db_path=db_path)

    assert isinstance(resolved, SQLiteMetadataStore)


def test_prune_service_resolve_config_memory(tmp_path: Path) -> None:
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "ws").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n[metadata]\nbackend = "memory"\n',
        encoding="utf-8",
    )

    service = PruneService()
    resolved = service.resolve_store(config_path=config_path)

    assert isinstance(resolved, InMemoryMetadataStore)


def test_prune_service_resolve_config_sqlite(tmp_path: Path) -> None:
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "ws").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n'
        '[metadata]\nbackend = "sqlite"\nsqlite_path = "nested/store.sqlite3"\n',
        encoding="utf-8",
    )

    service = PruneService()
    resolved = service.resolve_store(config_path=config_path)

    assert isinstance(resolved, SQLiteMetadataStore)


def test_prune_service_resolve_config_postgres_missing_dsn(tmp_path: Path) -> None:
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "ws").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n[metadata]\nbackend = "postgres"\n',
        encoding="utf-8",
    )

    service = PruneService()
    with pytest.raises(ValueError, match="metadata.postgres_dsn is required"):
        service.resolve_store(config_path=config_path)


def test_prune_service_resolve_explicit_dsn() -> None:
    service = PruneService()
    with patch("pyworkflowkit.cli.services.prune_service.PostgreSQLMetadataStore") as mock_pg:
        mock_instance = MagicMock()
        mock_pg.return_value = mock_instance

        resolved = service.resolve_store(dsn="postgresql://user:pass@localhost:5432/db")
        assert resolved == mock_instance
        mock_pg.assert_called_once_with("postgresql://user:pass@localhost:5432/db")


def test_prune_service_resolve_config_postgres_with_dsn(tmp_path: Path) -> None:
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "ws").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n'
        '[metadata]\nbackend = "postgres"\n'
        'postgres_dsn = "postgresql://user:pass@localhost:5432/db"\n',
        encoding="utf-8",
    )

    service = PruneService()
    with patch("pyworkflowkit.cli.services.prune_service.PostgreSQLMetadataStore") as mock_pg:
        mock_instance = MagicMock()
        mock_pg.return_value = mock_instance

        resolved = service.resolve_store(config_path=config_path)
        assert resolved == mock_instance
        assert mock_pg.call_count == 1
