"""Minimal plugin-authoring example through the public ecosystem SDK."""

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
            external_run_id=f"example-{context.task_run_id}",
            succeeded=True,
            output={"ok": True},
        )


def plugin() -> RegisteredPlugin[ExampleWorkload]:
    return plugin_registration(
        name="example-workload",
        plugin_type=PluginType.WORKLOAD,
        factory=ExampleWorkload,
        plugin_version="0.1.0",
        description="Minimal PyWorkflowKit external-workload plugin.",
    )


registration = plugin()
instance = registration.create()

print(
    json.dumps(
        {
            "name": registration.descriptor.name,
            "type": registration.descriptor.plugin_type.value,
            "instance": type(instance).__name__,
        },
        sort_keys=True,
    )
)
