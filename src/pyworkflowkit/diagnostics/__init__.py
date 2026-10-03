"""V2 structured diagnostics, failure evidence, and recovery inspection namespace."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from pyworkflowkit.application.inspection import RuntimeInspection, RuntimeInspector, TaskInspection
from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.diagnostics.model import Diagnostic, DiagnosticSeverity

if TYPE_CHECKING:
    from pyworkflowkit.diagnostics.recovery import (
        RecoveryAssessment,
        RecoveryDisposition,
        RecoveryInspector,
        TaskRecoveryAssessment,
    )

_RECOVERY_EXPORTS = frozenset(
    {
        "RecoveryAssessment",
        "RecoveryDisposition",
        "RecoveryInspector",
        "TaskRecoveryAssessment",
    }
)


def __getattr__(name: str) -> Any:
    if name in _RECOVERY_EXPORTS:
        module = import_module("pyworkflowkit.diagnostics.recovery")
        return getattr(module, name)
    raise AttributeError(name)


__all__ = [
    "Diagnostic",
    "DiagnosticSeverity",
    "FailureCategory",
    "FailureEvidence",
    "OutcomeUncertainty",
    "Retryability",
    "RecoveryAssessment",
    "RecoveryDisposition",
    "RecoveryInspector",
    "RuntimeInspection",
    "RuntimeInspector",
    "TaskInspection",
    "TaskRecoveryAssessment",
]
