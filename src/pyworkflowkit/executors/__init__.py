"""Canonical PyWorkflowKit V2 executor surface.

Legacy 1.1 executor contracts remain available from their historical module paths.
"""

from pyworkflowkit.executors.contracts import (
    Executor,
    ExecutorDescriptor,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from pyworkflowkit.executors.inline import InlineExecutor

__all__ = [
    "Executor",
    "ExecutorDescriptor",
    "InlineExecutor",
    "TaskExecutionContext",
    "TaskExecutionRequest",
    "TaskExecutionResult",
]
