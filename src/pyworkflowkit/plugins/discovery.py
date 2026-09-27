"""Opt-in plugin discovery through Python package entry points."""

from __future__ import annotations

import importlib.metadata as importlib_metadata
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pyworkflowkit.errors import (
    PluginCompatibilityError,
    PluginLoadError,
    PluginNotFoundError,
)
from pyworkflowkit.plugins.contracts import (
    ENTRY_POINT_GROUPS,
    assert_plugin_registration_compatible,
)
from pyworkflowkit.plugins.model import PluginDescriptor, PluginType
from pyworkflowkit.plugins.registry import PluginCatalog, RegisteredPlugin

class PluginDiscoveryStatus(StrEnum):
    """Lifecycle state of one discovered package entry point."""

    DISCOVERED = "discovered"
    LOADED = "loaded"
    INCOMPATIBLE = "incompatible"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DiscoveredPlugin:
    """Entry-point metadata collected without importing plugin code."""

    name: str
    plugin_type: PluginType
    group: str
    value: str
    distribution: str | None
    entry_point: Any


@dataclass(frozen=True, slots=True)
class PluginDiscoveryResult:
    """Outcome for one candidate during explicit enablement."""

    plugin: DiscoveredPlugin
    status: PluginDiscoveryStatus
    descriptor: PluginDescriptor | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PluginDiscoveryReport:
    """Deterministic report for discovered and explicitly enabled plugins."""

    results: tuple[PluginDiscoveryResult, ...]

    @property
    def has_errors(self) -> bool:
        return any(
            result.status
            in {
                PluginDiscoveryStatus.INCOMPATIBLE,
                PluginDiscoveryStatus.FAILED,
            }
            for result in self.results
        )


class PluginDiscovery:
    """Discover package metadata first and load only explicitly enabled plugins."""

    def discover(
        self,
        *,
        plugin_types: Collection[PluginType] | None = None,
    ) -> tuple[DiscoveredPlugin, ...]:
        selected_types = tuple(plugin_types or PluginType)
        entry_points = importlib_metadata.entry_points()
        discovered: list[DiscoveredPlugin] = []

        for plugin_type in selected_types:
            group = ENTRY_POINT_GROUPS[plugin_type]
            for entry_point in entry_points.select(group=group):
                distribution = getattr(getattr(entry_point, "dist", None), "name", None)
                discovered.append(
                    DiscoveredPlugin(
                        name=entry_point.name,
                        plugin_type=plugin_type,
                        group=group,
                        value=entry_point.value,
                        distribution=distribution,
                        entry_point=entry_point,
                    )
                )

        return tuple(
            sorted(
                discovered,
                key=lambda plugin: (plugin.plugin_type.value, plugin.name, plugin.value),
            )
        )

    def enable_selected(
        self,
        *,
        catalog: PluginCatalog,
        enabled: Mapping[PluginType, Collection[str]],
    ) -> PluginDiscoveryReport:
        """Load only selected candidate names and register compatible plugins."""

        candidates = self.discover(plugin_types=tuple(enabled))
        by_identity = {
            (candidate.plugin_type, candidate.name): candidate for candidate in candidates
        }

        missing = [
            (plugin_type, name)
            for plugin_type, names in enabled.items()
            for name in names
            if (plugin_type, name) not in by_identity
        ]
        if missing:
            plugin_type, name = sorted(
                missing,
                key=lambda item: (item[0].value, item[1]),
            )[0]
            raise PluginNotFoundError(
                plugin_name=name,
                plugin_type=plugin_type.value,
            )

        enabled_identities = {
            (plugin_type, name) for plugin_type, names in enabled.items() for name in names
        }
        results: list[PluginDiscoveryResult] = []

        for candidate in candidates:
            identity = (candidate.plugin_type, candidate.name)
            if identity not in enabled_identities:
                results.append(
                    PluginDiscoveryResult(
                        plugin=candidate,
                        status=PluginDiscoveryStatus.DISCOVERED,
                    )
                )
                continue
            results.append(self._enable_one(catalog=catalog, candidate=candidate))

        return PluginDiscoveryReport(results=tuple(results))

    def _enable_one(
        self,
        *,
        catalog: PluginCatalog,
        candidate: DiscoveredPlugin,
    ) -> PluginDiscoveryResult:
        try:
            loaded = candidate.entry_point.load()
            registration = loaded() if callable(loaded) else loaded
            if not isinstance(registration, RegisteredPlugin):
                raise PluginLoadError(
                    plugin_name=candidate.name,
                    reason=(
                        "entry point must resolve to RegisteredPlugin or "
                        "a zero-argument provider returning RegisteredPlugin"
                    ),
                )

            descriptor = registration.descriptor
            assert_plugin_registration_compatible(
                registration,
                entry_point_name=candidate.name,
                entry_point_group=candidate.group,
            )
            catalog.registry_for(candidate.plugin_type).register(
                descriptor,
                registration.factory,
            )
            return PluginDiscoveryResult(
                plugin=candidate,
                status=PluginDiscoveryStatus.LOADED,
                descriptor=descriptor,
            )
        except PluginCompatibilityError as exc:
            return PluginDiscoveryResult(
                plugin=candidate,
                status=PluginDiscoveryStatus.INCOMPATIBLE,
                error=str(exc),
            )
        except Exception as exc:
            error = (
                exc
                if isinstance(exc, PluginLoadError)
                else PluginLoadError(
                    plugin_name=candidate.name,
                    reason=f"{type(exc).__name__}: {exc}",
                )
            )
            return PluginDiscoveryResult(
                plugin=candidate,
                status=PluginDiscoveryStatus.FAILED,
                error=str(error),
            )

__all__ = [
    "ENTRY_POINT_GROUPS",
    "DiscoveredPlugin",
    "PluginDiscovery",
    "PluginDiscoveryReport",
    "PluginDiscoveryResult",
    "PluginDiscoveryStatus",
]
