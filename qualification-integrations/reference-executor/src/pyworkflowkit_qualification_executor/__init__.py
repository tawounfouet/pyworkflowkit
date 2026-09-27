"""Third-party executor fixture authored only through the ecosystem SDK."""

from __future__ import annotations

from collections.abc import Callable

from pyworkflowkit.ecosystem import (
    ExecutorCapabilities,
    PluginType,
    RunContext,
    TaskResult,
    plugin_registration,
)


class ReferenceExecutor:
    """Execute one context-aware trusted Python handler synchronously."""

    @property
    def key(self) -> str:
        return "reference-executor"

    @property
    def capabilities(self) -> ExecutorCapabilities:
        return ExecutorCapabilities()

    def execute(
        self,
        *,
        task: object,
        handler: Callable[[RunContext], object],
        context: RunContext,
    ) -> TaskResult:
        del task
        result = handler(context)
        if isinstance(result, TaskResult):
            return result
        return TaskResult(output=result)


def plugin():
    """Return the executor registration through the public ecosystem authoring helper."""

    return plugin_registration(
        name="reference-executor",
        plugin_type=PluginType.EXECUTOR,
        factory=ReferenceExecutor,
        plugin_version="0.1.0",
        description="Third-party executor fixture for 0.8 transverse qualification.",
    )


__all__ = ["ReferenceExecutor", "plugin"]
