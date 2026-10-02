"""Structured PyWorkflowKit V2 runtime diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pyworkflowkit.runtime.identity import CorrelationId


class DiagnosticSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


def _optional_text(value: str | None, *, field_name: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{field_name} must be a non-empty string when provided")


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Structured evidence explaining one runtime decision or anomaly."""

    code: str
    severity: DiagnosticSeverity
    summary: str
    details: tuple[tuple[str, str], ...] = ()
    workflow_run_id: str | None = None
    task_run_id: str | None = None
    task_attempt_id: str | None = None
    correlation_id: CorrelationId | None = None
    source_component: str | None = None
    decision_context: str | None = None
    related_policy: str | None = None
    source_framework: str = "pyworkflowkit"

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("diagnostic code must not be empty")
        if not isinstance(self.severity, DiagnosticSeverity):
            raise TypeError("severity must be a DiagnosticSeverity")
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("diagnostic summary must not be empty")

        if not isinstance(self.details, tuple):
            raise TypeError("details must be a tuple")
        for item in self.details:
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not all(isinstance(value, str) for value in item)
            ):
                raise TypeError("details must contain string key/value pairs")

        for name, value in (
            ("workflow_run_id", self.workflow_run_id),
            ("task_run_id", self.task_run_id),
            ("task_attempt_id", self.task_attempt_id),
            ("source_component", self.source_component),
            ("decision_context", self.decision_context),
            ("related_policy", self.related_policy),
        ):
            _optional_text(value, field_name=name)

        if self.correlation_id is not None and not isinstance(
            self.correlation_id,
            CorrelationId,
        ):
            raise TypeError("correlation_id must be a CorrelationId")
        if not isinstance(self.source_framework, str) or not self.source_framework.strip():
            raise ValueError("source_framework must not be empty")


__all__ = ["Diagnostic", "DiagnosticSeverity"]
