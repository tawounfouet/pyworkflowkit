"""Durable PostgreSQL implementation of the canonical V2 MetadataStore."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from pyworkflowkit.migrations import upgrade_database
from pyworkflowkit.persistence.sqlite import SQLiteMetadataStore

DEFAULT_V2_POSTGRES_APPLICATION_NAME = "pyworkflowkit-v2"


@dataclass(frozen=True, slots=True)
class PostgreSQLSettings:
    """Connection and pool settings for canonical V2 PostgreSQL persistence."""

    dsn: str
    pool_size: int = 5
    max_overflow: int = 10
    application_name: str = DEFAULT_V2_POSTGRES_APPLICATION_NAME

    def __post_init__(self) -> None:
        if not isinstance(self.dsn, str):
            raise TypeError("dsn must be a string")
        if not self.dsn.strip():
            raise ValueError("dsn must not be blank")
        if isinstance(self.pool_size, bool) or not isinstance(self.pool_size, int):
            raise TypeError("pool_size must be an integer")
        if self.pool_size < 1:
            raise ValueError("pool_size must be greater than or equal to 1")
        if isinstance(self.max_overflow, bool) or not isinstance(self.max_overflow, int):
            raise TypeError("max_overflow must be an integer")
        if self.max_overflow < 0:
            raise ValueError("max_overflow must be non-negative")
        if not isinstance(self.application_name, str):
            raise TypeError("application_name must be a string")
        if not self.application_name.strip():
            raise ValueError("application_name must not be blank")


def create_postgresql_engine(settings: PostgreSQLSettings) -> Engine:
    """Create the canonical V2 PostgreSQL engine.

    The connection contract is deliberately explicit: PostgreSQL only, READ COMMITTED,
    UTF-8, UTC session timezone, bounded SQLAlchemy pool and pre-ping before checkout.
    """

    if not isinstance(settings, PostgreSQLSettings):
        raise TypeError("settings must be PostgreSQLSettings")

    url = make_url(settings.dsn)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("PostgreSQLSettings.dsn must use a PostgreSQL SQLAlchemy URL")

    return create_engine(
        url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_pre_ping=True,
        isolation_level="READ COMMITTED",
        connect_args={
            "application_name": settings.application_name,
            "client_encoding": "UTF8",
            "options": "-c timezone=UTC",
        },
    )


class PostgreSQLMetadataStore(SQLiteMetadataStore):
    """Shared durable V2 MetadataStore backed by PostgreSQL.

    LOT-10 established the relational V2 persistence semantics in
    :class:`SQLiteMetadataStore`. Those methods are dialect-neutral SQLAlchemy
    operations over the canonical V2 rows. LOT-17 reuses that qualified relational
    behavior while replacing only the engine/bootstrap boundary with PostgreSQL.

    This inheritance is an implementation reuse detail; PostgreSQL does not inherit
    SQLite connection settings or SQLite PRAGMA behavior.
    """

    postgresql_settings: PostgreSQLSettings

    def __init__(
        self,
        dsn: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 10,
        application_name: str = DEFAULT_V2_POSTGRES_APPLICATION_NAME,
        create_schema: bool = True,
    ) -> None:
        self.postgresql_settings = PostgreSQLSettings(
            dsn=dsn,
            pool_size=pool_size,
            max_overflow=max_overflow,
            application_name=application_name,
        )
        self.engine = create_postgresql_engine(self.postgresql_settings)

        if create_schema:
            upgrade_database(self.engine)

        self._session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )


__all__ = [
    "DEFAULT_V2_POSTGRES_APPLICATION_NAME",
    "PostgreSQLMetadataStore",
    "PostgreSQLSettings",
    "create_postgresql_engine",
]
