"""Canonical V2 plugin contracts, registries and opt-in discovery.

The frozen PyWorkflowKit 1.1 plugin API remains available from
:mod:`pyworkflowkit.plugins`. LOT-16 introduces an additive V2 surface under
:mod:`pyworkflowkit.plugins.v2` so V1 registrations cannot be mistaken for V2
plugins.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

from pyworkflowkit.authoring.workloads import WorkloadDescriptor
from pyworkflowkit.errors import (
    DuplicatePluginError,
    PluginCompatibilityError,
    PluginLoadError,
    PluginNotFoundError,
    PluginTypeMismatchError,
)
from pyworkflowkit.executors import Executor
from pyworkflowkit.persistence import MetadataStore
from pyworkflowkit.plugins.model import PluginType
from pyworkflowkit.runtime import RuntimeEvent

V2_PLUGIN_API_VERSION = "2"
V2_PLUGIN_CONTRACT_VERSION = "1"

V2_ENTRY_POINT_GROUPS: Mapping[PluginType, str] = MappingProxyType(
    {
        PluginType.EXECUTOR: "pyworkflowkit.v2.executors",
        PluginType.METADATA: "pyworkflowkit.v2.metadata",
        PluginType.WORKLOAD: "pyworkflowkit.v2.workloads",
        PluginType.EVENT: "pyworkflowkit.v2.events",
    }
)
V2_PLUGIN_TYPE_BY_ENTRY_POINT_GROUP: Mapping[str, PluginType] = MappingProxyType(
    {group: plugin_type for plugin_type, group in V2_ENTRY_POINT_GROUPS.items()}
)


def _require_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")
    return value


@dataclass(frozen=True, slots=True)
class V2PluginDescriptor:
    """Immutable identity and compatibility metadata for one V2 plugin."""

    name: str
    plugin_type: PluginType
    api_version: str = V2_PLUGIN_API_VERSION
    plugin_version: str | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.name, field_name="plugin name")
        if not isinstance(self.plugin_type, PluginType):
            raise TypeError("plugin_type must be a PluginType")
        _require_text(self.api_version, field_name="plugin api_version")
        if self.plugin_version is not None:
            _require_text(self.plugin_version, field_name="plugin_version")
        if self.description is not None:
            _require_text(self.description, field_name="plugin description")


@dataclass(frozen=True, slots=True)
class V2WorkloadBinding:
    """Explicit V2 registered-workload binding supplied by a workload plugin."""

    registry_key: str
    handler: Callable[..., object]

    def __post_init__(self) -> None:
        _require_text(self.registry_key, field_name="registry_key")
        if not callable(self.handler):
            raise TypeError("handler must be callable")


@runtime_checkable
class V2RuntimeEventSink(Protocol):
    """Observe canonical V2 RuntimeEvent values after durable commit."""

    @property
    def name(self) -> str:
        """Stable sink identity used for diagnostics."""

    def emit(self, event: RuntimeEvent) -> None:
        """Observe one canonical V2 runtime event."""


T = TypeVar("T")
V2PluginFactory = Callable[[], T]


@dataclass(frozen=True, slots=True)
class V2RegisteredPlugin(Generic[T]):
    """One V2 descriptor paired with a lazy construction factory."""

    descriptor: V2PluginDescriptor
    factory: V2PluginFactory[T]

    def __post_init__(self) -> None:
        if not isinstance(self.descriptor, V2PluginDescriptor):
            raise TypeError("descriptor must be a V2PluginDescriptor")
        if not callable(self.factory):
            raise TypeError("factory must be callable")

    def create(self) -> T:
        """Create one plugin instance without discovery side effects."""

        return self.factory()


class V2PluginContractIssueCode(StrEnum):
    """Stable diagnostics emitted by the V2 plugin contract suite."""

    REGISTRATION_TYPE = "registration_type"
    ENTRY_POINT_GROUP = "entry_point_group"
    DESCRIPTOR_NAME = "descriptor_name"
    DESCRIPTOR_TYPE = "descriptor_type"
    API_VERSION = "api_version"
    FACTORY = "factory"
    INSTANCE_TYPE = "instance_type"


@dataclass(frozen=True, slots=True)
class V2PluginContractIssue:
    code: V2PluginContractIssueCode
    message: str


@dataclass(frozen=True, slots=True)
class V2PluginContractReport:
    entry_point_name: str
    entry_point_group: str
    descriptor: V2PluginDescriptor | None
    issues: tuple[V2PluginContractIssue, ...]

    @property
    def compatible(self) -> bool:
        return not self.issues

    @property
    def plugin_type(self) -> PluginType | None:
        return V2_PLUGIN_TYPE_BY_ENTRY_POINT_GROUP.get(self.entry_point_group)

    def summary(self) -> str:
        if self.compatible:
            return (
                f"plugin '{self.entry_point_name}' is compatible with "
                f"PyWorkflowKit V2 plugin API {V2_PLUGIN_API_VERSION}"
            )
        return "; ".join(issue.message for issue in self.issues)


@dataclass(frozen=True, slots=True)
class V2PluginInstanceContractReport:
    plugin_type: PluginType
    issues: tuple[V2PluginContractIssue, ...]

    @property
    def compatible(self) -> bool:
        return not self.issues

    def summary(self) -> str:
        if self.compatible:
            return f"{self.plugin_type.value} instance satisfies V2 plugin API"
        return "; ".join(issue.message for issue in self.issues)


def validate_v2_plugin_registration(
    registration: object,
    *,
    entry_point_name: str,
    entry_point_group: str,
) -> V2PluginContractReport:
    """Validate registration metadata without constructing a plugin instance."""

    _require_text(entry_point_name, field_name="entry_point_name")
    _require_text(entry_point_group, field_name="entry_point_group")
    issues: list[V2PluginContractIssue] = []
    expected_type = V2_PLUGIN_TYPE_BY_ENTRY_POINT_GROUP.get(entry_point_group)

    if expected_type is None:
        issues.append(
            V2PluginContractIssue(
                code=V2PluginContractIssueCode.ENTRY_POINT_GROUP,
                message=f"unknown PyWorkflowKit V2 entry-point group: {entry_point_group}",
            )
        )

    if not isinstance(registration, V2RegisteredPlugin):
        issues.append(
            V2PluginContractIssue(
                code=V2PluginContractIssueCode.REGISTRATION_TYPE,
                message=(
                    "V2 entry-point provider must return V2RegisteredPlugin; "
                    f"got {type(registration).__name__}"
                ),
            )
        )
        return V2PluginContractReport(
            entry_point_name=entry_point_name,
            entry_point_group=entry_point_group,
            descriptor=None,
            issues=tuple(issues),
        )

    descriptor = registration.descriptor
    if descriptor.name != entry_point_name:
        issues.append(
            V2PluginContractIssue(
                code=V2PluginContractIssueCode.DESCRIPTOR_NAME,
                message=(
                    f"descriptor name '{descriptor.name}' does not match "
                    f"entry-point name '{entry_point_name}'"
                ),
            )
        )
    if expected_type is not None and descriptor.plugin_type is not expected_type:
        issues.append(
            V2PluginContractIssue(
                code=V2PluginContractIssueCode.DESCRIPTOR_TYPE,
                message=(
                    f"descriptor type '{descriptor.plugin_type.value}' does not match "
                    f"entry-point group type '{expected_type.value}'"
                ),
            )
        )
    if descriptor.api_version != V2_PLUGIN_API_VERSION:
        issues.append(
            V2PluginContractIssue(
                code=V2PluginContractIssueCode.API_VERSION,
                message=(
                    f"plugin API version '{descriptor.api_version}' is incompatible with "
                    f"V2 runtime API version '{V2_PLUGIN_API_VERSION}'"
                ),
            )
        )
    if not callable(registration.factory):
        issues.append(
            V2PluginContractIssue(
                code=V2PluginContractIssueCode.FACTORY,
                message="V2RegisteredPlugin.factory must be callable",
            )
        )

    return V2PluginContractReport(
        entry_point_name=entry_point_name,
        entry_point_group=entry_point_group,
        descriptor=descriptor,
        issues=tuple(issues),
    )


def assert_v2_plugin_registration_compatible(
    registration: object,
    *,
    entry_point_name: str,
    entry_point_group: str,
) -> V2PluginContractReport:
    report = validate_v2_plugin_registration(
        registration,
        entry_point_name=entry_point_name,
        entry_point_group=entry_point_group,
    )
    if not report.compatible:
        raise PluginCompatibilityError(
            plugin_name=entry_point_name,
            reason=report.summary(),
        )
    return report


def validate_v2_plugin_instance(
    instance: object,
    *,
    plugin_type: PluginType,
) -> V2PluginInstanceContractReport:
    """Validate one explicitly-created instance against canonical V2 contracts."""

    if not isinstance(plugin_type, PluginType):
        raise TypeError("plugin_type must be a PluginType")

    compatible = False
    expected_name = ""
    if plugin_type is PluginType.EXECUTOR:
        compatible = isinstance(instance, Executor)
        expected_name = "pyworkflowkit.executors.Executor"
    elif plugin_type is PluginType.METADATA:
        compatible = isinstance(instance, MetadataStore)
        expected_name = "pyworkflowkit.persistence.MetadataStore"
    elif plugin_type is PluginType.WORKLOAD:
        compatible = isinstance(instance, V2WorkloadBinding)
        expected_name = "V2WorkloadBinding"
    else:
        compatible = isinstance(instance, V2RuntimeEventSink)
        expected_name = "V2RuntimeEventSink"

    issues: tuple[V2PluginContractIssue, ...] = ()
    if not compatible:
        issues = (
            V2PluginContractIssue(
                code=V2PluginContractIssueCode.INSTANCE_TYPE,
                message=(
                    f"{plugin_type.value} plugin instance does not satisfy "
                    f"{expected_name}"
                ),
            ),
        )
    return V2PluginInstanceContractReport(plugin_type=plugin_type, issues=issues)


def assert_v2_plugin_instance_compatible(
    instance: object,
    *,
    plugin_type: PluginType,
) -> V2PluginInstanceContractReport:
    report = validate_v2_plugin_instance(instance, plugin_type=plugin_type)
    if not report.compatible:
        raise PluginCompatibilityError(
            plugin_name=plugin_type.value,
            reason=report.summary(),
        )
    return report


class V2PluginRegistry(Generic[T]):
    """Typed registry for one canonical V2 extension category."""

    def __init__(self, *, plugin_type: PluginType) -> None:
        if not isinstance(plugin_type, PluginType):
            raise TypeError("plugin_type must be a PluginType")
        self._plugin_type = plugin_type
        self._plugins: dict[str, V2RegisteredPlugin[T]] = {}

    @property
    def plugin_type(self) -> PluginType:
        return self._plugin_type

    def register(self, registration: V2RegisteredPlugin[T]) -> None:
        if not isinstance(registration, V2RegisteredPlugin):
            raise TypeError("registration must be a V2RegisteredPlugin")
        descriptor = registration.descriptor
        if descriptor.plugin_type is not self._plugin_type:
            raise PluginTypeMismatchError(
                plugin_name=descriptor.name,
                expected_type=self._plugin_type.value,
                actual_type=descriptor.plugin_type.value,
            )
        if descriptor.api_version != V2_PLUGIN_API_VERSION:
            raise PluginCompatibilityError(
                plugin_name=descriptor.name,
                reason=(
                    f"plugin API version '{descriptor.api_version}' is incompatible with "
                    f"V2 runtime API version '{V2_PLUGIN_API_VERSION}'"
                ),
            )
        if descriptor.name in self._plugins:
            raise DuplicatePluginError(plugin_name=descriptor.name)
        self._plugins[descriptor.name] = registration

    def get(self, name: str) -> V2RegisteredPlugin[T]:
        try:
            return self._plugins[name]
        except KeyError as exc:
            raise PluginNotFoundError(
                plugin_name=name,
                plugin_type=self._plugin_type.value,
            ) from exc

    def create(self, name: str) -> T:
        instance = self.get(name).create()
        assert_v2_plugin_instance_compatible(instance, plugin_type=self._plugin_type)
        return instance

    def descriptors(self) -> tuple[V2PluginDescriptor, ...]:
        return tuple(self._plugins[name].descriptor for name in sorted(self._plugins))

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._plugins

    def __len__(self) -> int:
        return len(self._plugins)


class V2PluginCatalog:
    """Typed V2 plugin registries without implicit discovery or activation."""

    def __init__(self) -> None:
        self.executors: V2PluginRegistry[Executor] = V2PluginRegistry(
            plugin_type=PluginType.EXECUTOR
        )
        self.metadata: V2PluginRegistry[MetadataStore] = V2PluginRegistry(
            plugin_type=PluginType.METADATA
        )
        self.workloads: V2PluginRegistry[V2WorkloadBinding] = V2PluginRegistry(
            plugin_type=PluginType.WORKLOAD
        )
        self.events: V2PluginRegistry[V2RuntimeEventSink] = V2PluginRegistry(
            plugin_type=PluginType.EVENT
        )

    def registry_for(self, plugin_type: PluginType) -> V2PluginRegistry[object]:
        if plugin_type is PluginType.EXECUTOR:
            return _erase_registry(self.executors)
        if plugin_type is PluginType.METADATA:
            return _erase_registry(self.metadata)
        if plugin_type is PluginType.WORKLOAD:
            return _erase_registry(self.workloads)
        return _erase_registry(self.events)

    def descriptors(self) -> tuple[V2PluginDescriptor, ...]:
        values = [
            descriptor
            for registry in (
                self.executors,
                self.metadata,
                self.workloads,
                self.events,
            )
            for descriptor in registry.descriptors()
        ]
        return tuple(
            sorted(values, key=lambda item: (item.plugin_type.value, item.name))
        )


def _erase_registry(registry: V2PluginRegistry[T]) -> V2PluginRegistry[object]:
    return registry  # type: ignore[return-value]


class V2PluginDiscoveryStatus(StrEnum):
    DISCOVERED = "discovered"
    REGISTERED = "registered"
    INCOMPATIBLE = "incompatible"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class V2DiscoveredPlugin:
    """Entry-point metadata collected without importing plugin code."""

    name: str
    plugin_type: PluginType
    group: str
    value: str
    distribution: str | None
    entry_point: Any


@dataclass(frozen=True, slots=True)
class V2PluginDiscoveryResult:
    plugin: V2DiscoveredPlugin
    status: V2PluginDiscoveryStatus
    descriptor: V2PluginDescriptor | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class V2PluginDiscoveryReport:
    results: tuple[V2PluginDiscoveryResult, ...]

    @property
    def has_errors(self) -> bool:
        return any(
            result.status
            in {
                V2PluginDiscoveryStatus.INCOMPATIBLE,
                V2PluginDiscoveryStatus.FAILED,
            }
            for result in self.results
        )


class V2PluginDiscovery:
    """Metadata-first discovery with explicit V2-only enablement."""

    def discover(
        self,
        *,
        plugin_types: Collection[PluginType] | None = None,
    ) -> tuple[V2DiscoveredPlugin, ...]:
        selected_types = tuple(plugin_types or PluginType)
        entry_points = importlib_metadata.entry_points()
        discovered: list[V2DiscoveredPlugin] = []

        for plugin_type in selected_types:
            group = V2_ENTRY_POINT_GROUPS[plugin_type]
            for entry_point in entry_points.select(group=group):
                distribution = getattr(getattr(entry_point, "dist", None), "name", None)
                discovered.append(
                    V2DiscoveredPlugin(
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
                key=lambda item: (item.plugin_type.value, item.name, item.value),
            )
        )

    def enable_selected(
        self,
        *,
        catalog: V2PluginCatalog,
        enabled: Mapping[PluginType, Collection[str]],
    ) -> V2PluginDiscoveryReport:
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
            (plugin_type, name)
            for plugin_type, names in enabled.items()
            for name in names
        }
        results: list[V2PluginDiscoveryResult] = []
        for candidate in candidates:
            identity = (candidate.plugin_type, candidate.name)
            if identity not in enabled_identities:
                results.append(
                    V2PluginDiscoveryResult(
                        plugin=candidate,
                        status=V2PluginDiscoveryStatus.DISCOVERED,
                    )
                )
                continue
            results.append(self._enable_one(catalog=catalog, candidate=candidate))
        return V2PluginDiscoveryReport(results=tuple(results))

    def _enable_one(
        self,
        *,
        catalog: V2PluginCatalog,
        candidate: V2DiscoveredPlugin,
    ) -> V2PluginDiscoveryResult:
        try:
            loaded = candidate.entry_point.load()
            registration = loaded() if callable(loaded) else loaded
            assert_v2_plugin_registration_compatible(
                registration,
                entry_point_name=candidate.name,
                entry_point_group=candidate.group,
            )
            assert isinstance(registration, V2RegisteredPlugin)
            catalog.registry_for(candidate.plugin_type).register(registration)
            return V2PluginDiscoveryResult(
                plugin=candidate,
                status=V2PluginDiscoveryStatus.REGISTERED,
                descriptor=registration.descriptor,
            )
        except PluginCompatibilityError as exc:
            return V2PluginDiscoveryResult(
                plugin=candidate,
                status=V2PluginDiscoveryStatus.INCOMPATIBLE,
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
            return V2PluginDiscoveryResult(
                plugin=candidate,
                status=V2PluginDiscoveryStatus.FAILED,
                error=str(error),
            )


def v2_plugin_contract_snapshot() -> dict[str, object]:
    """Machine-readable LOT-16 compatibility contract."""

    return {
        "contract_version": V2_PLUGIN_CONTRACT_VERSION,
        "plugin_api_version": V2_PLUGIN_API_VERSION,
        "entry_point_groups": {
            plugin_type.value: group
            for plugin_type, group in V2_ENTRY_POINT_GROUPS.items()
        },
        "plugin_types": [plugin_type.value for plugin_type in PluginType],
        "executor_contract": "pyworkflowkit.executors.Executor",
        "metadata_contract": "pyworkflowkit.persistence.MetadataStore",
        "workload_contract": "V2WorkloadBinding",
        "event_contract": "V2RuntimeEventSink[pyworkflowkit.runtime.RuntimeEvent]",
        "metadata_first_discovery": True,
        "explicit_enablement": True,
        "implicit_v1_bridge": False,
        "instantiate_during_registration_validation": False,
    }


__all__ = [
    "V2DiscoveredPlugin",
    "V2PluginCatalog",
    "V2PluginContractIssue",
    "V2PluginContractIssueCode",
    "V2PluginContractReport",
    "V2PluginDescriptor",
    "V2PluginDiscovery",
    "V2PluginDiscoveryReport",
    "V2PluginDiscoveryResult",
    "V2PluginDiscoveryStatus",
    "V2PluginFactory",
    "V2PluginInstanceContractReport",
    "V2PluginRegistry",
    "V2RegisteredPlugin",
    "V2RuntimeEventSink",
    "V2WorkloadBinding",
    "V2_ENTRY_POINT_GROUPS",
    "V2_PLUGIN_API_VERSION",
    "V2_PLUGIN_CONTRACT_VERSION",
    "V2_PLUGIN_TYPE_BY_ENTRY_POINT_GROUP",
    "assert_v2_plugin_instance_compatible",
    "assert_v2_plugin_registration_compatible",
    "v2_plugin_contract_snapshot",
    "validate_v2_plugin_instance",
    "validate_v2_plugin_registration",
]
