"""Durable local SQLite MetadataStore adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from sqlalchemy import URL, Engine, create_engine, event
from sqlalchemy.orm import sessionmaker

from pyworkflowkit.adapters.metadata.sqlalchemy import DB_SCHEMA, SqlAlchemyMetadataStore
from pyworkflowkit.migrations import upgrade_database

DEFAULT_SQLITE_PATH = Path(".pyworkflow/state/pyworkflow.sqlite3")


@dataclass(frozen=True, slots=True)
class SQLiteSettings:
    """Local SQLite persistence settings."""

    path: Path = DEFAULT_SQLITE_PATH
    busy_timeout_ms: int = 5_000
    wal: bool = True

    def __post_init__(self) -> None:
        if self.busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must be non-negative")


def create_sqlite_engine(settings: SQLiteSettings) -> Engine:
    """Create a SQLite engine configured for PyWorkflowKit durability."""

    database_path = settings.path.expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        URL.create("sqlite+pysqlite", database=str(database_path)),
        execution_options={"schema_translate_map": {DB_SCHEMA: None}},
    )

    @event.listens_for(engine, "connect")
    def _configure_sqlite_connection(
        dbapi_connection: Any,
        connection_record: Any,
    ) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute(f"PRAGMA busy_timeout = {settings.busy_timeout_ms}")
            if settings.wal:
                cursor.execute("PRAGMA journal_mode = WAL")
        finally:
            cursor.close()

    return engine


class SQLiteMetadataStore(SqlAlchemyMetadataStore):
    """Durable single-machine MetadataStore backed by a SQLite file."""

    def __init__(
        self,
        path: str | Path = DEFAULT_SQLITE_PATH,
        *,
        busy_timeout_ms: int = 5_000,
        wal: bool = True,
        create_schema: bool = True,
    ) -> None:
        self.settings = SQLiteSettings(
            path=Path(path),
            busy_timeout_ms=busy_timeout_ms,
            wal=wal,
        )
        self.engine = create_sqlite_engine(self.settings)
        if create_schema:
            upgrade_database(self.engine)

        session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        super().__init__(session_factory)

    def close(self) -> None:
        """Release pooled SQLite connections."""

        self.engine.dispose()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()


__all__ = [
    "DEFAULT_SQLITE_PATH",
    "SQLiteMetadataStore",
    "SQLiteSettings",
    "create_sqlite_engine",
]
