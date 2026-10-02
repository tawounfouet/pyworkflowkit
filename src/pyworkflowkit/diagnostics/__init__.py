"""V2 structured diagnostics and failure-evidence namespace."""

from pyworkflowkit.application.inspection import RuntimeInspection, RuntimeInspector, TaskInspection
from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.diagnostics.model import Diagnostic, DiagnosticSeverity

__all__ = [
    "Diagnostic",
    "DiagnosticSeverity",
    "FailureCategory",
    "FailureEvidence",
    "OutcomeUncertainty",
    "Retryability",
    "RuntimeInspection",
    "RuntimeInspector",
    "TaskInspection",
]
