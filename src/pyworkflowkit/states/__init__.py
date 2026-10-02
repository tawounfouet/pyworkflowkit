"""Canonical PyWorkflowKit V2 lifecycle state surface."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from pyworkflowkit.states.enums import (
    BlockReason,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)

if TYPE_CHECKING:
    from pyworkflowkit.states.machine import (
        TaskAttemptStateMachine,
        TaskRunStateMachine,
        WorkflowRunStateMachine,
    )

_MACHINE_EXPORTS = frozenset(
    {
        "TaskAttemptStateMachine",
        "TaskRunStateMachine",
        "WorkflowRunStateMachine",
    }
)


def __getattr__(name: str) -> Any:
    if name in _MACHINE_EXPORTS:
        module = import_module("pyworkflowkit.states.machine")
        return getattr(module, name)
    raise AttributeError(name)


__all__ = [
    "BlockReason",
    "SkipReason",
    "TaskAttemptStateMachine",
    "TaskAttemptStatus",
    "TaskRunStateMachine",
    "TaskRunStatus",
    "WorkflowRunStateMachine",
    "WorkflowRunStatus",
]
