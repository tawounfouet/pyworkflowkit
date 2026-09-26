"""Programmatic Alembic migration entry points."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine

MIGRATIONS_ROOT = Path(__file__).resolve().parent


def alembic_config(*, engine: Engine | None = None, url: str | None = None) -> Config:
    """Build an Alembic Config from migrations packaged with PyWorkflowKit."""

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_ROOT))
    if url is not None:
        config.set_main_option("sqlalchemy.url", url)
    if engine is not None:
        config.attributes["engine"] = engine
    return config


def upgrade_database(engine: Engine, revision: str = "head") -> None:
    """Upgrade a relational metadata database to the requested revision."""

    command.upgrade(alembic_config(engine=engine), revision)


def current_revision(engine: Engine) -> str | None:
    """Return the current Alembic revision for an engine."""

    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return context.get_current_revision()


__all__ = [
    "MIGRATIONS_ROOT",
    "alembic_config",
    "current_revision",
    "upgrade_database",
]
