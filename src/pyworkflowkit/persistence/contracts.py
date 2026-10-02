"""Canonical PyWorkflowKit V2 metadata persistence contracts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pyworkflowkit.runtime.entities import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId
from pyworkflowkit.runtime.references import ExternalRunRef
from pyworkflowkit.states import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus


class StateEntityType(StrEnum):
    WORKFLOW_RUN = "workflow_run"
    TASK_RUN = "task_run"
    TASK_ATTEMPT = "task_attempt"


@dataclass(frozen=True, slots=True)
class MetadataStoreMetadata:
    """Machine-readable capabilities and schema identity for one metadata store."""

    contract_version: str
    schema_version: str
    durable: bool
    supports_concurrent_writers: bool
    supports_atomic_batch: bool

    def __post_init__(self) -> None:
        if not self.contract_version.strip():
            raise ValueError("contract_version must not be empty")
        if not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")


@dataclass(frozen=True, slots=True)
class StateTransitionRecord:
    """Append-only evidence that one persisted runtime status changed."""

    sequence: int
    entity_type: StateEntityType
    entity_id: str
    from_status: str | None
    to_status: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int):
            raise TypeError("sequence must be an integer")
        if self.sequence < 1:
            raise ValueError("sequence must be greater than or equal to 1")
        if not isinstance(self.entity_type, StateEntityType):
            raise TypeError("entity_type must be a StateEntityType")
        if not self.entity_id.strip():
            raise ValueError("entity_id must not be empty")
        if self.from_status is not None and not self.from_status.strip():
            raise ValueError("from_status must not be empty when provided")
        if not self.to_status.strip():
            raise ValueError("to_status must not be empty")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ManifestReference:
    """Provisional hook to a manifest owned by the later manifest contract."""

    locator: str
    schema_version: str
    digest: str | None = None

    def __post_init__(self) -> None:
        if not self.locator.strip():
            raise ValueError("locator must not be empty")
        if not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")
        if self.digest is not None and not self.digest.strip():
            raise ValueError("digest must not be empty when provided")


@runtime_checkable
class MetadataStore(Protocol):
    """Persistence port for canonical V2 runtime state."""

    def metadata(self) -> MetadataStoreMetadata:
        """Return store contract/schema metadata without external side effects."""

    def create_workflow_run(self, run: WorkflowRun) -> None:
        """Persist a newly-created WorkflowRun."""

    def get_workflow_run(self, run_id: WorkflowRunId) -> WorkflowRun:
        """Load one WorkflowRun or raise MetadataNotFoundError."""

    def update_workflow_run(
        self,
        run: WorkflowRun,
        *,
        expected_status: WorkflowRunStatus,
        transitioned_at: datetime | None = None,
    ) -> None:
        """Conditionally replace WorkflowRun state."""

    def list_workflow_runs(self) -> Sequence[WorkflowRun]:
        """Return all WorkflowRuns in deterministic identity order."""

    def list_unfinished_workflow_runs(self) -> Sequence[WorkflowRun]:
        """Return non-terminal WorkflowRuns in deterministic identity order."""

    def create_task_run(self, task_run: TaskRun) -> None:
        """Persist a newly-created TaskRun."""

    def get_task_run(self, task_run_id: TaskRunId) -> TaskRun:
        """Load one TaskRun or raise MetadataNotFoundError."""

    def update_task_run(
        self,
        task_run: TaskRun,
        *,
        expected_status: TaskRunStatus,
        transitioned_at: datetime | None = None,
    ) -> None:
        """Conditionally replace TaskRun state."""

    def list_task_runs(self, workflow_run_id: WorkflowRunId) -> Sequence[TaskRun]:
        """Return TaskRuns belonging to one WorkflowRun."""

    def append_task_attempt(self, attempt: TaskAttempt) -> None:
        """Append one immutable attempt identity to TaskRun history."""

    def get_task_attempt(self, attempt_id: TaskAttemptId) -> TaskAttempt:
        """Load one TaskAttempt or raise MetadataNotFoundError."""

    def update_task_attempt(
        self,
        attempt: TaskAttempt,
        *,
        expected_status: TaskAttemptStatus,
        transitioned_at: datetime | None = None,
    ) -> None:
        """Conditionally replace TaskAttempt state."""

    def list_task_attempts(self, task_run_id: TaskRunId) -> Sequence[TaskAttempt]:
        """Return attempts in ascending attempt-number order."""

    def append_external_run_ref(
        self,
        *,
        attempt_id: TaskAttemptId,
        external_ref: ExternalRunRef,
    ) -> None:
        """Persist one external execution reference for a TaskAttempt."""

    def list_external_run_refs(
        self,
        attempt_id: TaskAttemptId,
    ) -> Sequence[ExternalRunRef]:
        """Return deterministic external execution references for an attempt."""

    def list_state_transitions(
        self,
        *,
        entity_type: StateEntityType | None = None,
        entity_id: str | None = None,
    ) -> Sequence[StateTransitionRecord]:
        """Query append-only persisted state history."""

    def set_manifest_reference(
        self,
        run_id: WorkflowRunId,
        reference: ManifestReference,
    ) -> None:
        """Persist the manifest reference hook for one WorkflowRun."""

    def get_manifest_reference(self, run_id: WorkflowRunId) -> ManifestReference:
        """Load a manifest reference or raise MetadataNotFoundError."""


__all__ = [
    "ManifestReference",
    "MetadataStore",
    "MetadataStoreMetadata",
    "StateEntityType",
    "StateTransitionRecord",
]
