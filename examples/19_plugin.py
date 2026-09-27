"""Canonical plugin-authoring example through the public ecosystem SDK."""

from __future__ import annotations

import json

from pyworkflowkit.ecosystem import (
    ExternalWorkloadResult,
    PluginType,
    RegisteredPlugin,
    RunContext,
    plugin_registration,
)


class ExampleWorkload:
    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        return ExternalWorkloadResult(
            external_run_id=f"plugin-{context.task_run_id}",
            succeeded=True,
        )


def plugin() -> RegisteredPlugin[ExampleWorkload]:
    return plugin_registration(
        name="example-workload",
        plugin_type=PluginType.WORKLOAD,
        factory=ExampleWorkload,
        plugin_version="0.1.0",
        description="Canonical PyWorkflowKit workload plugin example.",
    )


registration = plugin()
instance = registration.create()

print(
    json.dumps(
        {
            "instance": type(instance).__name__,
            "name": registration.descriptor.name,
            "type": registration.descriptor.plugin_type.value,
        },
        sort_keys=True,
    )
)
