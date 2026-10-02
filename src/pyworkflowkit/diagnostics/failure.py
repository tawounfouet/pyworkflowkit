"""Structured failure, retryability and uncertainty evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from pyworkflowkit.runtime.identity import CorrelationId
from pyworkflowkit.runtime.references import ExternalRunRef


class FailureCategory(StrEnum):
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    CAPABILITY = "capability"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    TRANSIENT = "transient"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    RATE_LIMITED = "rate_limited"
    INTEGRITY = "integrity"
    CONTRACT_VIOLATION = "contract_violation"
    SIDE_EFFECT_FAILED = "side_effect_failed"
    UNKNOWN_OUTCOME = "unknown_outcome"
    INTERNAL = "internal"
    EXTERNAL_PROVIDER = "external_provider"


class Retryability(StrEnum):
    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"
    UNKNOWN = "unknown"
    RETRYABLE_AFTER_RECONCILIATION = "retryable_after_reconciliation"


class OutcomeUncertainty(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"
    REQUIRES_RECONCILIATION = "requires_reconciliation"


def _optional_text(value: str | None, *, field_name: str) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ValueError(f"{field_name} must be a non-empty string when provided")


def _validate_details(details: tuple[tuple[str, str], ...]) -> None:
    if not isinstance(details, tuple):
        raise TypeError("details must be a tuple")
    for item in details:
        if (
            not isinstance(item, tuple)
            or len(item) != 2
            or not all(isinstance(value, str) for value in item)
        ):
            raise TypeError("details must contain string key/value pairs")


@dataclass(frozen=True, slots=True)
class FailureEvidence:
    """Durable machine-readable evidence for failed or uncertain workflow work."""

    error_code: str
    category: FailureCategory
    retryability: Retryability
    uncertainty: OutcomeUncertainty
    correlation_id: CorrelationId
    source_framework: str = "pyworkflowkit"
    workflow_run_id: str | None = None
    task_run_id: str | None = None
    task_attempt_id: str | None = None
    external_run: ExternalRunRef | None = None
    source_component: str | None = None
    provider_code: str | None = None
    message_summary: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    details: tuple[tuple[str, str], ...] = ()
    contract_version: str = "1"

    def __post_init__(self) -> None:
        if not isinstance(self.error_code, str) or not self.error_code.strip():
            raise ValueError("error_code must not be empty")
        if not isinstance(self.category, FailureCategory):
            raise TypeError("category must be a FailureCategory")
        if not isinstance(self.retryability, Retryability):
            raise TypeError("retryability must be a Retryability")
        if not isinstance(self.uncertainty, OutcomeUncertainty):
            raise TypeError("uncertainty must be an OutcomeUncertainty")
        if not isinstance(self.correlation_id, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")
        if not isinstance(self.source_framework, str) or not self.source_framework.strip():
            raise ValueError("source_framework must not be empty")

        for name, value in (
            ("workflow_run_id", self.workflow_run_id),
            ("task_run_id", self.task_run_id),
            ("task_attempt_id", self.task_attempt_id),
            ("source_component", self.source_component),
            ("provider_code", self.provider_code),
            ("message_summary", self.message_summary),
        ):
            _optional_text(value, field_name=name)

        if self.external_run is not None and not isinstance(self.external_run, ExternalRunRef):
            raise TypeError("external_run must be an ExternalRunRef")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")

        _validate_details(self.details)
        if not isinstance(self.contract_version, str) or not self.contract_version.strip():
            raise ValueError("contract_version must not be empty")


__all__ = [
    "FailureCategory",
    "FailureEvidence",
    "OutcomeUncertainty",
    "Retryability",
]
