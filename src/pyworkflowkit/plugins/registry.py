"""Typed manual plugin registries.

M22 intentionally supports explicit registration only. Automatic discovery via
importlib.metadata entry points belongs to M23.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pyworkflowkit.errors import (
    DuplicatePluginError,
    PluginNotFoundError,
    PluginTypeMismatchError,
)
from pyworkflowkit.plugins.model import PluginDescriptor, PluginType
from pyworkflowkit.ports.executor import Executor
from pyworkflowkit.ports.metadata_store import MetadataStore

T = TypeVar("T")
PluginFactory = Callable[[], T]


@dataclass(frozen=True, slots=True)
class RegisteredPlugin(Generic[T]):
    """One descriptor paired with a typed construction factory."""

    descriptor: PluginDescriptor
    factory: PluginFactory[T]

    def create(self) -> T:
        """Create one plugin instance."""

        return self.factory()


class PluginRegistry(Generic[T]):
    """Registry for one explicit PluginType."""

    def __init__(self, *, plugin_type: PluginType) -> None:
        self._plugin_type = plugin_type
        self._plugins: dict[str, RegisteredPlugin[T]] = {}

    @property
    def plugin_type(self) -> PluginType:
        return self._plugin_type

    def register(
        self,
        descriptor: PluginDescriptor,
        factory: PluginFactory[T],
    ) -> None:
        """Register one plugin factory under its stable descriptor name."""

        if descriptor.plugin_type is not self._plugin_type:
            raise PluginTypeMismatchError(
                plugin_name=descriptor.name,
                expected_type=self._plugin_type.value,
                actual_type=descriptor.plugin_type.value,
            )
        if descriptor.name in self._plugins:
            raise DuplicatePluginError(plugin_name=descriptor.name)

        self._plugins[descriptor.name] = RegisteredPlugin(
            descriptor=descriptor,
            factory=factory,
        )

    def get(self, name: str) -> RegisteredPlugin[T]:
        """Return one registration or raise a public plugin error."""

        try:
            return self._plugins[name]
        except KeyError as exc:
            raise PluginNotFoundError(
                plugin_name=name,
                plugin_type=self._plugin_type.value,
            ) from exc

    def create(self, name: str) -> T:
        """Create one plugin instance from the registered factory."""

        return self.get(name).create()

    def descriptors(self) -> tuple[PluginDescriptor, ...]:
        """Return registered descriptors in deterministic name order."""

        return tuple(self._plugins[name].descriptor for name in sorted(self._plugins))

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._plugins

    def __len__(self) -> int:
        return len(self._plugins)


class PluginCatalog:
    """Typed registries for current PyWorkflowKit extension categories."""

    def __init__(self) -> None:
        self.executors: PluginRegistry[Executor] = PluginRegistry(plugin_type=PluginType.EXECUTOR)
        self.metadata: PluginRegistry[MetadataStore] = PluginRegistry(
            plugin_type=PluginType.METADATA
        )
        self.workloads: PluginRegistry[object] = PluginRegistry(plugin_type=PluginType.WORKLOAD)
        self.events: PluginRegistry[object] = PluginRegistry(plugin_type=PluginType.EVENT)

    def registry_for(self, plugin_type: PluginType) -> PluginRegistry[object]:
        """Return a type-erased registry for generic inspection tooling."""

        if plugin_type is PluginType.EXECUTOR:
            return _erase_registry(self.executors)
        if plugin_type is PluginType.METADATA:
            return _erase_registry(self.metadata)
        if plugin_type is PluginType.WORKLOAD:
            return self.workloads
        return self.events

    def descriptors(self) -> tuple[PluginDescriptor, ...]:
        """Return all manually registered descriptors deterministically."""

        registries = (
            self.executors,
            self.metadata,
            self.workloads,
            self.events,
        )
        descriptors = [
            descriptor for registry in registries for descriptor in registry.descriptors()
        ]
        return tuple(
            sorted(
                descriptors,
                key=lambda value: (value.plugin_type.value, value.name),
            )
        )


def _erase_registry(registry: PluginRegistry[T]) -> PluginRegistry[object]:
    # The registry API is read/write, so this cast-like helper remains internal
    # and is used only by generic inspection tooling. Typed callers should use
    # the concrete catalog properties.
    return registry  # type: ignore[return-value]


__all__ = [
    "PluginCatalog",
    "PluginFactory",
    "PluginRegistry",
    "RegisteredPlugin",
]
