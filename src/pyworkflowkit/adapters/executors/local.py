"""Synchronous same-process LocalExecutor."""

import logging

from pyworkflowkit.adapters.executors._python import invoke_python_handler
from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.values import TaskResult
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    ExecutorCapabilities,
    RunContext,
    TaskHandler,
    TimeoutCapability,
)

logger = logging.getLogger("pyworkflowkit.executor.local")


class LocalExecutor:
    """Execute trusted Python handlers synchronously in the current process."""

    _CAPABILITIES = ExecutorCapabilities(
        supports_parallelism=False,
        timeout=TimeoutCapability.NONE,
        cancellation=CancellationCapability.NONE,
        max_concurrency=1,
    )

    @property
    def key(self) -> str:
        return "local"

    @property
    def capabilities(self) -> ExecutorCapabilities:
        return self._CAPABILITIES

    def execute(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> TaskResult:
        return invoke_python_handler(
            task=task,
            handler=handler,
            context=context,
            executor_key=self.key,
            logger=logger,
        )


__all__ = ["LocalExecutor"]
