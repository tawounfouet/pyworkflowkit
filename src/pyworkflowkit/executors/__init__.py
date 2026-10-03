"""Canonical PyWorkflowKit V2 executor surface.

Legacy 1.1 executor contracts remain available from their historical module paths.
"""

from pyworkflowkit.executors.contracts import (
    V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS,
    V2_EXECUTOR_CONTRACT_VERSION,
    V2_EXECUTOR_PROTOCOL_METHODS,
    CancellableExecutor,
    CancellationCapability,
    CancellationStatus,
    Executor,
    ExecutorDescriptor,
    TaskCancellationRequest,
    TaskCancellationResult,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
    v2_executor_contract_snapshot,
)
from pyworkflowkit.executors.asyncio import AsyncExecutor
from pyworkflowkit.executors.inline import InlineExecutor
from pyworkflowkit.executors.process import ProcessExecutor
from pyworkflowkit.executors.registry import ExecutorRegistry
from pyworkflowkit.executors.subprocess import (
    SubprocessCommand,
    SubprocessExecutor,
    SubprocessResult,
    SubprocessSecurityPolicy,
)
from pyworkflowkit.executors.thread import ThreadExecutor

__all__ = [
    "AsyncExecutor",
    "CancellationCapability",
    "CancellationStatus",
    "CancellableExecutor",
    "Executor",
    "ExecutorDescriptor",
    "ExecutorRegistry",
    "InlineExecutor",
    "ProcessExecutor",
    "SubprocessCommand",
    "SubprocessExecutor",
    "SubprocessResult",
    "SubprocessSecurityPolicy",
    "TaskCancellationRequest",
    "TaskCancellationResult",
    "TaskExecutionContext",
    "TaskExecutionRequest",
    "TaskExecutionResult",
    "ThreadExecutor",
    "V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS",
    "V2_EXECUTOR_CONTRACT_VERSION",
    "V2_EXECUTOR_PROTOCOL_METHODS",
    "v2_executor_contract_snapshot",
]
