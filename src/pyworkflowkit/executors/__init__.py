"""Canonical PyWorkflowKit V2 executor surface.

Legacy 1.1 executor contracts remain available from their historical module paths.
"""

from pyworkflowkit.executors.contracts import (
    V2_EXECUTOR_CONTRACT_VERSION,
    V2_EXECUTOR_PROTOCOL_METHODS,
    Executor,
    ExecutorDescriptor,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
    v2_executor_contract_snapshot,
)
from pyworkflowkit.executors.inline import InlineExecutor

__all__ = [
    "Executor",
    "ExecutorDescriptor",
    "InlineExecutor",
    "TaskExecutionContext",
    "TaskExecutionRequest",
    "TaskExecutionResult",
    "V2_EXECUTOR_CONTRACT_VERSION",
    "V2_EXECUTOR_PROTOCOL_METHODS",
    "v2_executor_contract_snapshot",
]
