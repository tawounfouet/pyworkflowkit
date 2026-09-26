"""Composition root for validated local runtime settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.metadata.postgres import PostgresMetadataStore
from pyworkflowkit.adapters.metadata.sqlite import SQLiteMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.ports.executor import Executor
from pyworkflowkit.ports.metadata_store import MetadataStore


@dataclass(frozen=True, slots=True)
class RuntimeComponents:
    """Explicitly composed runtime components."""

    settings: RuntimeSettings
    runner: Runner
    metadata_store: MetadataStore
    handler_registry: HandlerRegistry
    executor: Executor


class RuntimeFactory:
    """Compose built-in runtime adapters from validated settings."""

    @classmethod
    def build(
        cls,
        settings: RuntimeSettings | None = None,
        *,
        handler_registry: HandlerRegistry | None = None,
    ) -> RuntimeComponents:
        resolved = settings or RuntimeSettings()
        registry = handler_registry or HandlerRegistry()
        executor = LocalExecutor()
        metadata_store = cls._build_metadata_store(resolved)

        runner = Runner(
            metadata_store=metadata_store,
            handler_registry=registry,
            executor=executor,
            clock=SystemClock(),
            id_factory=UuidRuntimeIdFactory(),
            sleeper=SystemSleeper(),
        )

        return RuntimeComponents(
            settings=resolved,
            runner=runner,
            metadata_store=metadata_store,
            handler_registry=registry,
            executor=executor,
        )

    @staticmethod
    def _build_metadata_store(settings: RuntimeSettings) -> MetadataStore:
        metadata = settings.metadata

        if metadata.backend == "memory":
            return MemoryMetadataStore()

        if metadata.backend == "sqlite":
            path = metadata.sqlite_path
            if not path.is_absolute():
                path = Path(settings.runtime.workspace) / path
            return SQLiteMetadataStore(
                path,
                busy_timeout_ms=metadata.sqlite_busy_timeout_ms,
                wal=metadata.sqlite_wal,
            )

        if metadata.backend == "postgres":
            if metadata.postgres_dsn is None:
                raise ValueError("metadata.postgres_dsn is required for postgres backend")
            return PostgresMetadataStore(
                metadata.postgres_dsn.get_secret_value(),
                pool_size=metadata.postgres_pool_size,
                max_overflow=metadata.postgres_max_overflow,
                application_name=metadata.postgres_application_name,
            )

        raise ValueError(f"unsupported metadata backend: {metadata.backend}")


__all__ = ["RuntimeComponents", "RuntimeFactory"]
