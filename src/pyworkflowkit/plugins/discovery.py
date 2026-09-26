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
from pyworkflowkit.plugins.model import PLUGIN_API_VERSION, PluginDescriptor, PluginType
from pyworkflowkit.plugins.registry import PluginCatalog, RegisteredPlugin

ENTRY_POINT_GROUPS: Mapping[PluginType, str] = {
    PluginType.EXECUTOR: "pyworkflowkit.executors",
    PluginType.METADATA: "pyworkflowkit.metadata",
    PluginType.WORKLOAD: "pyworkflowkit.workloads",
    PluginType.EVENT: "pyworkflowkit.events",
}


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
            (candidate.plugin_type, candidate.name): candidate
            for candidate in candidates
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
            (plugin_type, name)
            for plugin_type, names in enabled.items()
            for name in names
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
            self._validate_compatibility(candidate=candidate, descriptor=descriptor)
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

    @staticmethod
    def _validate_compatibility(
        *,
        candidate: DiscoveredPlugin,
        descriptor: PluginDescriptor,
    ) -> None:
        if descriptor.name != candidate.name:
            raise PluginCompatibilityError(
                plugin_name=candidate.name,
                reason=(
                    f"descriptor name '{descriptor.name}' does not match "
                    f"entry-point name '{candidate.name}'"
                ),
            )
        if descriptor.plugin_type is not candidate.plugin_type:
            raise PluginCompatibilityError(
                plugin_name=candidate.name,
                reason=(
                    f"descriptor type '{descriptor.plugin_type.value}' does not match "
                    f"entry-point group type '{candidate.plugin_type.value}'"
                ),
            )
        if descriptor.api_version != PLUGIN_API_VERSION:
            raise PluginCompatibilityError(
                plugin_name=candidate.name,
                reason=(
                    f"plugin API version '{descriptor.api_version}' is incompatible with "
                    f"runtime API version '{PLUGIN_API_VERSION}'"
                ),
            )


__all__ = [
    "ENTRY_POINT_GROUPS",
    "DiscoveredPlugin",
    "PluginDiscovery",
    "PluginDiscoveryReport",
    "PluginDiscoveryResult",
    "PluginDiscoveryStatus",
]
