"""Public plugin ecosystem compatibility contracts for PyWorkflowKit."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from pyworkflowkit.errors import PluginCompatibilityError
from pyworkflowkit.plugins.model import PLUGIN_API_VERSION, PluginDescriptor, PluginType
from pyworkflowkit.plugins.registry import RegisteredPlugin
from pyworkflowkit.ports.executor import Executor
from pyworkflowkit.ports.metadata_store import MetadataStore
from pyworkflowkit.ports.observability import RuntimeEventSink

ENTRY_POINT_GROUPS: Mapping[PluginType, str] = MappingProxyType(
    {
        PluginType.EXECUTOR: "pyworkflowkit.executors",
        PluginType.METADATA: "pyworkflowkit.metadata",
        PluginType.WORKLOAD: "pyworkflowkit.workloads",
        PluginType.EVENT: "pyworkflowkit.events",
    }
)

PLUGIN_TYPE_BY_ENTRY_POINT_GROUP: Mapping[str, PluginType] = MappingProxyType(
    {group: plugin_type for plugin_type, group in ENTRY_POINT_GROUPS.items()}
)


class PluginContractIssueCode(StrEnum):
    """Stable diagnostic codes emitted by the plugin contract suite."""

    REGISTRATION_TYPE = "registration_type"
    ENTRY_POINT_GROUP = "entry_point_group"
    DESCRIPTOR_NAME = "descriptor_name"
    DESCRIPTOR_TYPE = "descriptor_type"
    API_VERSION = "api_version"
    FACTORY = "factory"
    INSTANCE_TYPE = "instance_type"


@dataclass(frozen=True, slots=True)
class PluginContractIssue:
    """One deterministic compatibility finding."""

    code: PluginContractIssueCode
    message: str


@dataclass(frozen=True, slots=True)
class PluginContractReport:
    """Compatibility report for one entry-point registration."""

    entry_point_name: str
    entry_point_group: str
    descriptor: PluginDescriptor | None
    issues: tuple[PluginContractIssue, ...]

    @property
    def compatible(self) -> bool:
        return not self.issues

    @property
    def plugin_type(self) -> PluginType | None:
        return PLUGIN_TYPE_BY_ENTRY_POINT_GROUP.get(self.entry_point_group)

    @property
    def messages(self) -> tuple[str, ...]:
        return tuple(issue.message for issue in self.issues)

    def summary(self) -> str:
        if self.compatible:
            return (
                f"plugin '{self.entry_point_name}' is compatible with "
                f"PyWorkflowKit plugin API {PLUGIN_API_VERSION}"
            )
        return "; ".join(self.messages)


@dataclass(frozen=True, slots=True)
class PluginInstanceContractReport:
    """Structural compatibility report for an explicitly created plugin instance."""

    plugin_type: PluginType
    issues: tuple[PluginContractIssue, ...]

    @property
    def compatible(self) -> bool:
        return not self.issues

    @property
    def messages(self) -> tuple[str, ...]:
        return tuple(issue.message for issue in self.issues)

    def summary(self) -> str:
        if self.compatible:
            return f"{self.plugin_type.value} instance satisfies plugin API {PLUGIN_API_VERSION}"
        return "; ".join(self.messages)


def validate_plugin_registration(
    registration: object,
    *,
    entry_point_name: str,
    entry_point_group: str,
) -> PluginContractReport:
    """Validate metadata compatibility without creating the plugin instance."""

    issues: list[PluginContractIssue] = []
    expected_type = PLUGIN_TYPE_BY_ENTRY_POINT_GROUP.get(entry_point_group)

    if expected_type is None:
        issues.append(
            PluginContractIssue(
                code=PluginContractIssueCode.ENTRY_POINT_GROUP,
                message=f"unknown PyWorkflowKit entry-point group: {entry_point_group}",
            )
        )

    if not isinstance(registration, RegisteredPlugin):
        issues.append(
            PluginContractIssue(
                code=PluginContractIssueCode.REGISTRATION_TYPE,
                message=(
                    "entry-point provider must return RegisteredPlugin; "
                    f"got {type(registration).__name__}"
                ),
            )
        )
        return PluginContractReport(
            entry_point_name=entry_point_name,
            entry_point_group=entry_point_group,
            descriptor=None,
            issues=tuple(issues),
        )

    descriptor = registration.descriptor

    if descriptor.name != entry_point_name:
        issues.append(
            PluginContractIssue(
                code=PluginContractIssueCode.DESCRIPTOR_NAME,
                message=(
                    f"descriptor name '{descriptor.name}' does not match "
                    f"entry-point name '{entry_point_name}'"
                ),
            )
        )

    if expected_type is not None and descriptor.plugin_type is not expected_type:
        issues.append(
            PluginContractIssue(
                code=PluginContractIssueCode.DESCRIPTOR_TYPE,
                message=(
                    f"descriptor type '{descriptor.plugin_type.value}' does not match "
                    f"entry-point group type '{expected_type.value}'"
                ),
            )
        )

    if descriptor.api_version != PLUGIN_API_VERSION:
        issues.append(
            PluginContractIssue(
                code=PluginContractIssueCode.API_VERSION,
                message=(
                    f"plugin API version '{descriptor.api_version}' is incompatible with "
                    f"runtime API version '{PLUGIN_API_VERSION}'"
                ),
            )
        )

    if not callable(registration.factory):
        issues.append(
            PluginContractIssue(
                code=PluginContractIssueCode.FACTORY,
                message="RegisteredPlugin.factory must be callable",
            )
        )

    return PluginContractReport(
        entry_point_name=entry_point_name,
        entry_point_group=entry_point_group,
        descriptor=descriptor,
        issues=tuple(issues),
    )


def assert_plugin_registration_compatible(
    registration: object,
    *,
    entry_point_name: str,
    entry_point_group: str,
) -> PluginContractReport:
    """Return a compatible report or raise the public compatibility error."""

    report = validate_plugin_registration(
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


def validate_plugin_instance(
    instance: object,
    *,
    plugin_type: PluginType,
) -> PluginInstanceContractReport:
    """Validate an already-created instance without invoking a plugin factory."""

    if not isinstance(plugin_type, PluginType):
        raise TypeError("plugin_type must be a PluginType")

    expected_protocol: type[object] | None
    if plugin_type is PluginType.EXECUTOR:
        expected_protocol = Executor
    elif plugin_type is PluginType.METADATA:
        expected_protocol = MetadataStore
    elif plugin_type is PluginType.EVENT:
        expected_protocol = RuntimeEventSink
    else:
        expected_protocol = None

    issues: tuple[PluginContractIssue, ...] = ()
    if expected_protocol is not None and not isinstance(instance, expected_protocol):
        issues = (
            PluginContractIssue(
                code=PluginContractIssueCode.INSTANCE_TYPE,
                message=(
                    f"{plugin_type.value} plugin instance does not satisfy "
                    f"{expected_protocol.__name__}"
                ),
            ),
        )

    return PluginInstanceContractReport(
        plugin_type=plugin_type,
        issues=issues,
    )


def assert_plugin_instance_compatible(
    instance: object,
    *,
    plugin_type: PluginType,
) -> PluginInstanceContractReport:
    """Return an instance report or raise PluginCompatibilityError."""

    report = validate_plugin_instance(instance, plugin_type=plugin_type)
    if not report.compatible:
        raise PluginCompatibilityError(
            plugin_name=plugin_type.value,
            reason=report.summary(),
        )
    return report


__all__ = [
    "ENTRY_POINT_GROUPS",
    "PLUGIN_TYPE_BY_ENTRY_POINT_GROUP",
    "PluginContractIssue",
    "PluginContractIssueCode",
    "PluginContractReport",
    "PluginInstanceContractReport",
    "assert_plugin_instance_compatible",
    "assert_plugin_registration_compatible",
    "validate_plugin_instance",
    "validate_plugin_registration",
]
