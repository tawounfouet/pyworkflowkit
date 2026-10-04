"""Service orchestrating metadata store historical pruning and lifecycle policies."""

from __future__ import annotations

from pathlib import Path

from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.persistence.contracts import MetadataStore
from pyworkflowkit.persistence.memory import InMemoryMetadataStore
from pyworkflowkit.persistence.postgresql import PostgreSQLMetadataStore
from pyworkflowkit.persistence.retention import PruneReport, RetentionPolicy
from pyworkflowkit.persistence.sqlite import SQLiteMetadataStore


class PruneService:
    """Service orchestrating store historical pruning with safe defaults."""

    def __init__(
        self,
        store: MetadataStore | None = None,
        *,
        workspace: Path | None = None,
    ) -> None:
        self._store = store
        self._workspace = workspace

    def resolve_store(
        self,
        *,
        db_path: Path | None = None,
        dsn: str | None = None,
        config_path: Path | None = None,
    ) -> MetadataStore:
        if self._store is not None:
            return self._store

        if dsn:
            return PostgreSQLMetadataStore(dsn)

        if db_path:
            return SQLiteMetadataStore(path=db_path)

        settings = (
            RuntimeSettings()
            if config_path is None
            else RuntimeSettings.load(config_file=config_path)
        )
        metadata = settings.metadata

        if metadata.backend == "postgres":
            if metadata.postgres_dsn is None:
                raise ValueError("metadata.postgres_dsn is required for postgres backend")
            return PostgreSQLMetadataStore(
                metadata.postgres_dsn.get_secret_value(),
                pool_size=metadata.postgres_pool_size,
                max_overflow=metadata.postgres_max_overflow,
                application_name=metadata.postgres_application_name,
            )

        if metadata.backend == "memory":
            return InMemoryMetadataStore()

        sqlite_path = metadata.sqlite_path
        if not sqlite_path.is_absolute():
            base_dir = self._workspace or Path(settings.runtime.workspace)
            sqlite_path = base_dir / sqlite_path
        return SQLiteMetadataStore(path=sqlite_path)

    def prune(
        self,
        policy: RetentionPolicy,
        *,
        dry_run: bool = False,
        batch_size: int = 500,
        db_path: Path | None = None,
        dsn: str | None = None,
        config_path: Path | None = None,
    ) -> PruneReport:
        store = self.resolve_store(db_path=db_path, dsn=dsn, config_path=config_path)
        return store.prune_runs(policy, dry_run=dry_run, batch_size=batch_size)


__all__ = ["PruneService"]
