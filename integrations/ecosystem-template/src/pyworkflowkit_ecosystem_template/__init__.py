"""Reference third-party package using only the public ecosystem SDK."""

from __future__ import annotations

from pyworkflowkit.ecosystem import (
    ExternalWorkloadResult,
    PluginType,
    RegisteredPlugin,
    RunContext,
    plugin_registration,
)


class TemplateWorkload:
    """Minimal external workload used to prove the authoring experience."""

    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        return ExternalWorkloadResult(
            external_run_id=f"template-{context.task_run_id}",
            succeeded=True,
            output={"template": True},
            uri=f"urn:pyworkflowkit:ecosystem-template:{context.task_run_id}",
            metadata={"sdk": "pyworkflowkit.ecosystem"},
        )


def plugin() -> RegisteredPlugin[TemplateWorkload]:
    """Return a self-checked Plugin API registration."""

    return plugin_registration(
        name="ecosystem-template",
        plugin_type=PluginType.WORKLOAD,
        factory=TemplateWorkload,
        plugin_version="0.1.0",
        description="Reference workload integration authored through the ecosystem SDK.",
    )


__all__ = ["TemplateWorkload", "plugin"]
