"""Independently packaged reference workload integration."""

from __future__ import annotations

from pyworkflowkit.integrations import ExternalWorkloadResult
from pyworkflowkit.plugins import (
    PLUGIN_API_VERSION,
    PluginDescriptor,
    PluginType,
    RegisteredPlugin,
)
from pyworkflowkit.ports.executor import RunContext


class ReferenceExternalWorkload:
    """One foreign-style workload implemented outside pyworkflowkit core."""

    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        return ExternalWorkloadResult(
            external_run_id=f"reference-{context.task_run_id}",
            succeeded=True,
            output={"source": "reference-workload"},
            uri=f"urn:pyworkflowkit:reference-workload:{context.task_run_id}",
            metadata={"reference": True},
        )


def plugin() -> RegisteredPlugin[ReferenceExternalWorkload]:
    """Return the workload plugin registration exposed through entry points."""

    return RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="reference-workload",
            plugin_type=PluginType.WORKLOAD,
            api_version=PLUGIN_API_VERSION,
            plugin_version="0.1.0",
            description="Reference independently packaged ExternalWorkload.",
        ),
        factory=ReferenceExternalWorkload,
    )


__all__ = ["ReferenceExternalWorkload", "plugin"]
