"""External-run reconciliation port."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pyworkflowkit.domain.values import ExternalRunRef


class ExternalRunStatus(StrEnum):
    """Normalized status returned by an external-run verifier."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


@runtime_checkable
class ExternalRunVerifier(Protocol):
    """Provider-specific status verifier for one ExternalRunRef."""

    @property
    def provider(self) -> str:
        """Provider key handled by this verifier."""

    def verify(self, external_ref: ExternalRunRef) -> ExternalRunStatus:
        """Return the current normalized status for one external execution."""


__all__ = ["ExternalRunStatus", "ExternalRunVerifier"]
