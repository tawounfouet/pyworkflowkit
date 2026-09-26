"""Programmatic Alembic migration entry points."""

from __future__ import annotations

from importlib.resources import as_file, files

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine


def alembic_config(*, engine: Engine | None = None, url: str | None = None) -> Config:
    """Build an Alembic Config from migrations packaged with PyWorkflowKit."""

    migrations_root = files("pyworkflowkit.migrations")
    with as_file(migrations_root) as path:
        config = Config()
        config.set_main_option("script_location", str(path))
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


__all__ = ["alembic_config", "current_revision", "upgrade_database"]
