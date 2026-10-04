"""Third-party executor fixture authored only through the ecosystem SDK."""

from __future__ import annotations

from collections.abc import Callable
from inspect import signature
from typing import cast

from pyworkflowkit.ecosystem import (
    ExecutorCapabilities,
    PluginType,
    RegisteredPlugin,
    RunContext,
    TaskDefinition,
    TaskHandler,
    TaskResult,
    plugin_registration,
)


class ReferenceExecutor:
    """Execute trusted Python handlers synchronously through the public SDK."""

    @property
    def key(self) -> str:
        return "reference-executor"

    @property
    def capabilities(self) -> ExecutorCapabilities:
        return ExecutorCapabilities()

    def execute(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> TaskResult:
        del task
        if len(signature(handler).parameters) == 0:
            result = cast(Callable[[], object], handler)()
        else:
            result = cast(Callable[[RunContext], object], handler)(context)
        if isinstance(result, TaskResult):
            return result
        return TaskResult(output=result)


def plugin() -> RegisteredPlugin[ReferenceExecutor]:
    """Return the executor registration through the public ecosystem authoring helper."""

    return plugin_registration(
        name="reference-executor",
        plugin_type=PluginType.EXECUTOR,
        factory=ReferenceExecutor,
        plugin_version="0.1.0",
        description="Third-party executor fixture for 0.8 transverse qualification.",
    )


__all__ = ["ReferenceExecutor", "plugin"]
