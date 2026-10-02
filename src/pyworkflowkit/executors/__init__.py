"""V2 executor namespace baseline.

LOT-06 rewrites the Executor protocol around TaskExecutionRequest/Result and
renames LocalExecutor to InlineExecutor. The exports here are transitional.
"""

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    Executor,
    ExecutorCapabilities,
    RunContext,
    TimeoutCapability,
)

__all__ = [
    "CancellationCapability",
    "Executor",
    "ExecutorCapabilities",
    "LocalExecutor",
    "RunContext",
    "ThreadExecutor",
    "TimeoutCapability",
]
