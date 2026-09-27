"""Canonical custom Executor protocol example."""

from __future__ import annotations

import json

from pyworkflowkit.ecosystem import (
    Executor,
    ExecutorCapabilities,
    RunContext,
    TaskDefinition,
    TaskHandler,
    TaskResult,
)


class InlineExampleExecutor:
    key = "inline-example"

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
        del task, handler, context
        return TaskResult(output="example")


executor = InlineExampleExecutor()

print(
    json.dumps(
        {
            "conforms_to_executor_protocol": isinstance(executor, Executor),
            "key": executor.key,
            "max_concurrency": executor.capabilities.max_concurrency,
        },
        sort_keys=True,
    )
)
