"""Tests for the runtime composition root."""

from pathlib import Path

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.metadata.sqlite import SQLiteMetadataStore
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.factory import RuntimeFactory
from pyworkflowkit.config import RuntimeSettings


def test_default_factory_composes_memory_and_local_executor() -> None:
    components = RuntimeFactory.build()

    assert isinstance(components.metadata_store, MemoryMetadataStore)
    assert isinstance(components.executor, LocalExecutor)
    assert isinstance(components.handler_registry, HandlerRegistry)


def test_factory_preserves_explicit_handler_registry() -> None:
    registry = HandlerRegistry()

    components = RuntimeFactory.build(handler_registry=registry)

    assert components.handler_registry is registry


def test_factory_composes_sqlite_under_workspace(tmp_path: Path) -> None:
    settings = RuntimeSettings.model_validate(
        {
            "runtime": {"workspace": tmp_path},
            "metadata": {
                "backend": "sqlite",
                "sqlite_path": "state/runtime.sqlite3",
                "sqlite_wal": False,
            },
        }
    )

    components = RuntimeFactory.build(settings)

    assert isinstance(components.metadata_store, SQLiteMetadataStore)
    assert components.metadata_store.settings.path == tmp_path / "state/runtime.sqlite3"
    components.metadata_store.close()
