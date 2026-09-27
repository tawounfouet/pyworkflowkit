"""Reusable ecosystem conformance helpers without a pytest dependency."""

from __future__ import annotations

from dataclasses import dataclass

from pyworkflowkit.errors import PluginCompatibilityError
from pyworkflowkit.plugins import (
    PluginContractIssue,
    PluginType,
    RegisteredPlugin,
    validate_plugin_instance,
    validate_plugin_registration,
)


@dataclass(frozen=True, slots=True)
class EcosystemConformanceReport:
    """Combined registration and instance conformance for one plugin."""

    plugin_name: str
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
            return f"{self.plugin_type.value} plugin '{self.plugin_name}' conforms"
        return "; ".join(self.messages)


def validate_plugin_conformance(
    registration: object,
    *,
    entry_point_name: str,
    plugin_type: PluginType,
    create_instance: bool = True,
) -> EcosystemConformanceReport:
    """Validate registration metadata and the structural contract owned by Plugin API v1.

    WORKLOAD intentionally remains an open plugin category at this level. A workload
    plugin may itself be an ExternalWorkload or may be an adapter/factory that creates
    one. The M47 ExternalWorkload protocol is validated when the produced workload is
    actually composed for execution, not by narrowing the generic Plugin API category.
    """

    from pyworkflowkit.ecosystem.authoring import entry_point_group

    registration_report = validate_plugin_registration(
        registration,
        entry_point_name=entry_point_name,
        entry_point_group=entry_point_group(plugin_type),
    )
    issues = list(registration_report.issues)

    if create_instance and isinstance(registration, RegisteredPlugin) and not issues:
        instance_report = validate_plugin_instance(
            registration.create(),
            plugin_type=plugin_type,
        )
        issues.extend(instance_report.issues)

    return EcosystemConformanceReport(
        plugin_name=entry_point_name,
        plugin_type=plugin_type,
        issues=tuple(issues),
    )


def assert_plugin_conforms(
    registration: object,
    *,
    entry_point_name: str,
    plugin_type: PluginType,
    create_instance: bool = True,
) -> EcosystemConformanceReport:
    """Return a compatible report or raise the stable PluginCompatibilityError."""

    report = validate_plugin_conformance(
        registration,
        entry_point_name=entry_point_name,
        plugin_type=plugin_type,
        create_instance=create_instance,
    )
    if not report.compatible:
        raise PluginCompatibilityError(
            plugin_name=entry_point_name,
            reason=report.summary(),
        )
    return report


__all__ = [
    "EcosystemConformanceReport",
    "assert_plugin_conforms",
    "validate_plugin_conformance",
]
