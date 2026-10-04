"""Canonical PyWorkflowKit V2 metadata persistence contracts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pyworkflowkit.persistence.retention import (
    DeletedRecordsSummary,
    PruneReport,
    RetentionPolicy,
)
from pyworkflowkit.runtime.entities import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.runtime.evidence import RuntimeEvent, TaskOutputCheckpoint
from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId
from pyworkflowkit.runtime.references import ExternalRunRef
from pyworkflowkit.states import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus

V2_METADATA_STORE_CONTRACT_VERSION = "2"

V2_METADATA_STORE_METHODS: tuple[str, ...] = (
    "metadata",
    "create_workflow_run",
    "get_workflow_run",
    "update_workflow_run",
    "list_workflow_runs",
    "list_unfinished_workflow_runs",
    "create_task_run",
    "get_task_run",
    "update_task_run",
    "list_task_runs",
    "append_task_attempt",
    "get_task_attempt",
    "update_task_attempt",
    "list_task_attempts",
    "append_external_run_ref",
    "list_external_run_refs",
    "list_state_transitions",
    "list_runtime_events",
    "set_task_output_checkpoint",
    "get_task_output_checkpoint",
    "set_manifest_reference",
    "get_manifest_reference",
)


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
        for name, text_value in (
            ("contract_version", self.contract_version),
            ("schema_version", self.schema_version),
        ):
            if not isinstance(text_value, str):
                raise TypeError(f"{name} must be a string")
            if not text_value.strip():
                raise ValueError(f"{name} must not be empty")
        for name, flag_value in (
            ("durable", self.durable),
            ("supports_concurrent_writers", self.supports_concurrent_writers),
            ("supports_atomic_batch", self.supports_atomic_batch),
        ):
            if not isinstance(flag_value, bool):
                raise TypeError(f"{name} must be a bool")


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
        if not isinstance(self.entity_id, str):
            raise TypeError("entity_id must be a string")
        if not self.entity_id.strip():
            raise ValueError("entity_id must not be empty")
        if self.from_status is not None:
            if not isinstance(self.from_status, str):
                raise TypeError("from_status must be a string when provided")
            if not self.from_status.strip():
                raise ValueError("from_status must not be empty when provided")
        if not isinstance(self.to_status, str):
            raise TypeError("to_status must be a string")
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
        for name, value in (
            ("locator", self.locator),
            ("schema_version", self.schema_version),
        ):
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.digest is not None:
            if not isinstance(self.digest, str):
                raise TypeError("digest must be a string when provided")
            if not self.digest.strip():
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

    def list_runtime_events(
        self,
        workflow_run_id: WorkflowRunId,
    ) -> Sequence[RuntimeEvent]:
        """Project canonical runtime events from durable state-transition evidence."""

    def set_task_output_checkpoint(
        self,
        checkpoint: TaskOutputCheckpoint,
    ) -> None:
        """Persist one immutable portable output checkpoint for a TaskRun."""

    def get_task_output_checkpoint(
        self,
        task_run_id: TaskRunId,
    ) -> TaskOutputCheckpoint:
        """Load durable portable output evidence or raise MetadataNotFoundError."""

    def set_manifest_reference(
        self,
        run_id: WorkflowRunId,
        reference: ManifestReference,
    ) -> None:
        """Persist the manifest reference hook for one WorkflowRun."""

    def get_manifest_reference(self, run_id: WorkflowRunId) -> ManifestReference:
        """Load a manifest reference or raise MetadataNotFoundError."""

    def prune_runs(
        self,
        policy: RetentionPolicy,
        *,
        dry_run: bool = False,
        batch_size: int = 500,
        now: datetime | None = None,
    ) -> PruneReport:
        """Purge historical runs according to the retention policy."""


def v2_metadata_store_contract_snapshot() -> dict[str, object]:
    return {
        "contract_version": V2_METADATA_STORE_CONTRACT_VERSION,
        "methods": list(V2_METADATA_STORE_METHODS),
        "state_entity_types": [value.value for value in StateEntityType],
    }


__all__ = [
    "DeletedRecordsSummary",
    "ManifestReference",
    "MetadataStore",
    "MetadataStoreMetadata",
    "PruneReport",
    "RetentionPolicy",
    "StateEntityType",
    "StateTransitionRecord",
    "V2_METADATA_STORE_CONTRACT_VERSION",
    "V2_METADATA_STORE_METHODS",
    "v2_metadata_store_contract_snapshot",
]
