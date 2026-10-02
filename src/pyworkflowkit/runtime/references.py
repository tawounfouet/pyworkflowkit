"""Portable references crossing the PyWorkflowKit runtime boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pyworkflowkit.runtime.identity import CorrelationId, WorkflowRunId


def _require_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _validate_pairs(
    values: tuple[tuple[str, str], ...],
    *,
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{field_name} must be a tuple")
    for item in values:
        if (
            not isinstance(item, tuple)
            or len(item) != 2
            or not all(isinstance(value, str) for value in item)
        ):
            raise TypeError(f"{field_name} must contain string key/value pairs")


@dataclass(frozen=True, slots=True)
class WorkflowExecutionReference:
    """Portable reference to one PyWorkflowKit WorkflowRun."""

    workflow_run_id: WorkflowRunId
    workflow_definition_id: str
    status: str | None = None
    started_at: datetime | None = None
    owner: str = "pyworkflowkit"
    namespace: str = "pyworkflowkit.workflow_execution"
    contract_version: str = "1"

    def __post_init__(self) -> None:
        if not isinstance(self.workflow_run_id, WorkflowRunId):
            raise TypeError("workflow_run_id must be a WorkflowRunId")
        _require_text(self.workflow_definition_id, field_name="workflow_definition_id")

        if self.status is not None:
            _require_text(self.status, field_name="status")
        if self.started_at is not None and (
            self.started_at.tzinfo is None or self.started_at.utcoffset() is None
        ):
            raise ValueError("started_at must be timezone-aware when provided")

        _require_text(self.owner, field_name="owner")
        _require_text(self.namespace, field_name="namespace")
        _require_text(self.contract_version, field_name="contract_version")


@dataclass(frozen=True, slots=True)
class ExternalRunRef:
    """Authority-neutral reference to execution owned outside PyWorkflowKit."""

    provider: str
    external_run_id: str
    kind: str
    status_hint: str | None = None
    status_locator: str | None = None
    correlation_id: CorrelationId | None = None
    causation_id: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()
    namespace: str = "pyworkflowkit.external_run"
    contract_version: str = "1"

    def __post_init__(self) -> None:
        _require_text(self.provider, field_name="provider")
        _require_text(self.external_run_id, field_name="external_run_id")
        _require_text(self.kind, field_name="kind")

        if self.status_hint is not None:
            _require_text(self.status_hint, field_name="status_hint")
        if self.status_locator is not None:
            _require_text(self.status_locator, field_name="status_locator")
        if self.correlation_id is not None and not isinstance(
            self.correlation_id,
            CorrelationId,
        ):
            raise TypeError("correlation_id must be a CorrelationId")
        if self.causation_id is not None:
            _require_text(self.causation_id, field_name="causation_id")

        _validate_pairs(self.metadata, field_name="metadata")
        _require_text(self.namespace, field_name="namespace")
        _require_text(self.contract_version, field_name="contract_version")


__all__ = ["ExternalRunRef", "WorkflowExecutionReference"]
