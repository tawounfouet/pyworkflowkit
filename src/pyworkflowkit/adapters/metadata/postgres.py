"""Shared/concurrent PostgreSQL MetadataStore adapter."""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Self

from sqlalchemy import Engine, create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from pyworkflowkit.adapters.metadata.sqlalchemy import Base, SqlAlchemyMetadataStore
from pyworkflowkit.adapters.metadata.sqlalchemy import models as orm_models
from pyworkflowkit.adapters.metadata.sqlalchemy.mapping import SqlAlchemyRowMapper
from pyworkflowkit.adapters.metadata.sqlalchemy.store import SqlAlchemyUnitOfWork
from pyworkflowkit.adapters.persistence.mapping import PersistenceMapper
from pyworkflowkit.domain.ids import TaskRunId
from pyworkflowkit.domain.runtime import TaskRun
from pyworkflowkit.errors import MetadataNotFoundError

DEFAULT_POSTGRES_SCHEMA = "pyworkflowkit"


@dataclass(frozen=True, slots=True)
class PostgresSettings:
    """Connection and pool settings for PostgreSQL persistence."""

    dsn: str
    pool_size: int = 5
    max_overflow: int = 10
    application_name: str = "pyworkflowkit"

    def __post_init__(self) -> None:
        if self.pool_size < 1:
            raise ValueError("pool_size must be >= 1")
        if self.max_overflow < 0:
            raise ValueError("max_overflow must be non-negative")
        if not self.application_name.strip():
            raise ValueError("application_name must not be blank")


def create_postgres_engine(settings: PostgresSettings) -> Engine:
    """Create a PostgreSQL engine using READ COMMITTED isolation."""

    url = make_url(settings.dsn)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("PostgresSettings.dsn must use a PostgreSQL SQLAlchemy URL")

    return create_engine(
        url,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        isolation_level="READ COMMITTED",
        connect_args={"application_name": settings.application_name},
    )


class PostgresMetadataStore(SqlAlchemyMetadataStore):
    """Production-oriented shared MetadataStore backed by PostgreSQL."""

    def __init__(
        self,
        dsn: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 10,
        application_name: str = "pyworkflowkit",
        create_schema: bool = True,
    ) -> None:
        self.settings = PostgresSettings(
            dsn=dsn,
            pool_size=pool_size,
            max_overflow=max_overflow,
            application_name=application_name,
        )
        self.engine = create_postgres_engine(self.settings)

        if create_schema:
            with self.engine.begin() as connection:
                connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DEFAULT_POSTGRES_SCHEMA}"))
                connection.execute(text("SET TIME ZONE 'UTC'"))
                Base.metadata.create_all(connection)

        session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )
        super().__init__(session_factory)

    def unit_of_work(self) -> PostgresUnitOfWork:
        return PostgresUnitOfWork(self._session_factory)

    def close(self) -> None:
        """Release pooled PostgreSQL connections."""

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


class PostgresUnitOfWork(SqlAlchemyUnitOfWork):
    """SQLAlchemy UoW with explicit PostgreSQL row-lock support."""

    def lock_task_run(self, task_run_id: TaskRunId) -> TaskRun:
        session = self._require_session()
        row = session.scalar(
            select(orm_models.TaskRunRow)
            .where(orm_models.TaskRunRow.task_run_id == str(task_run_id))
            .with_for_update()
        )
        if row is None:
            raise MetadataNotFoundError(entity_type="TaskRun", entity_id=str(task_run_id))
        return PersistenceMapper.task_run_from_row(SqlAlchemyRowMapper.task_run_from_orm(row))


__all__ = [
    "DEFAULT_POSTGRES_SCHEMA",
    "PostgresMetadataStore",
    "PostgresSettings",
    "PostgresUnitOfWork",
    "create_postgres_engine",
]
