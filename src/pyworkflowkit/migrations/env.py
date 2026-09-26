"""Alembic environment for PyWorkflowKit metadata persistence."""

from __future__ import annotations

from alembic import context
from sqlalchemy import Engine, create_engine, pool, text
from sqlalchemy.engine import Connection

from pyworkflowkit.adapters.metadata.sqlalchemy import models as _models  # noqa: F401
from pyworkflowkit.adapters.metadata.sqlalchemy.base import DB_SCHEMA, Base

config = context.config
target_metadata = Base.metadata


def _configure(connection: Connection) -> None:
    if connection.dialect.name == "postgresql":
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}"))
        connection.commit()

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_engine = config.attributes.get("engine")
    if isinstance(supplied_engine, Engine):
        with supplied_engine.connect() as connection:
            _configure(connection)
        return

    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("sqlalchemy.url is required when no Engine is supplied.")
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        _configure(connection)


if context.is_offline_mode():
    raise RuntimeError("PyWorkflowKit migrations require online mode.")

run_migrations_online()
