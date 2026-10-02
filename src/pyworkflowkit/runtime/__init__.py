"""Canonical PyWorkflowKit V2 runtime surface.

The frozen package root still exposes the 1.1 WorkflowRuntime until the final V2
root migration. Qualified `pyworkflowkit.runtime` owns the canonical V2 runtime.

Heavy runtime orchestration/result imports are lazy so low-level identity/context
modules remain safe dependencies of executor and persistence contracts.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from pyworkflowkit.domain.runtime import RuntimeEvent
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.entities import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.runtime.identity import (
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.runtime.references import ExternalRunRef, WorkflowExecutionReference
from pyworkflowkit.runtime.services import (
    Clock,
    RetryWaiter,
    RuntimeIdentityFactory,
    SystemClock,
    SystemRetryWaiter,
    UuidRuntimeIdentityFactory,
)

if TYPE_CHECKING:
    from pyworkflowkit.runtime.results import CancellationResult, TaskOutcome, WorkflowResult
    from pyworkflowkit.runtime.workflow import WorkflowRuntime

_LAZY_EXPORTS = {
    "CancellationResult": ("pyworkflowkit.runtime.results", "CancellationResult"),
    "TaskOutcome": ("pyworkflowkit.runtime.results", "TaskOutcome"),
    "WorkflowResult": ("pyworkflowkit.runtime.results", "WorkflowResult"),
    "WorkflowRuntime": ("pyworkflowkit.runtime.workflow", "WorkflowRuntime"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    module = import_module(module_name)
    return getattr(module, attribute)


__all__ = [
    "CancellationResult",
    "Clock",
    "CorrelationContext",
    "CorrelationId",
    "ExternalRunRef",
    "RuntimeEvent",
    "RetryWaiter",
    "RuntimeIdentityFactory",
    "SystemClock",
    "SystemRetryWaiter",
    "TaskAttempt",
    "TaskAttemptId",
    "TaskOutcome",
    "TaskRun",
    "TaskRunId",
    "UuidRuntimeIdentityFactory",
    "WorkflowExecutionReference",
    "WorkflowResult",
    "WorkflowRun",
    "WorkflowRunId",
    "WorkflowRuntime",
]
