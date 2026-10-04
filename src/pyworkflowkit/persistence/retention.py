"""Retention policy and prune reporting models for persistence lifecycle management."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pyworkflowkit.states.enums import WORKFLOW_TERMINAL_STATUSES, WorkflowRunStatus

DEFAULT_PRUNE_STATES: tuple[WorkflowRunStatus, ...] = (
    WorkflowRunStatus.SUCCEEDED,
    WorkflowRunStatus.CANCELLED,
)


class RetentionPolicy(BaseModel):
    """Declarative specification for historical metadata retention and pruning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retention_days: int | None = Field(
        default=30,
        ge=1,
        description="Maximum age in days of completed runs to retain.",
    )
    max_runs_per_workflow: int | None = Field(
        default=100,
        ge=1,
        description="Maximum number of recent runs to keep per workflow name.",
    )
    prune_states: Sequence[WorkflowRunStatus] = Field(
        default_factory=lambda: list(DEFAULT_PRUNE_STATES),
        description="Target workflow terminal statuses eligible for pruning.",
    )
    retain_failed_runs_days: int | None = Field(
        default=90,
        ge=1,
        description="Extended retention days specifically for FAILED workflow runs.",
    )
    workflow_names: Sequence[str] | None = Field(
        default=None,
        description="Optional list of workflow names to restrict pruning to.",
    )

    @field_validator("prune_states")
    @classmethod
    def validate_prune_states(
        cls, states: Sequence[WorkflowRunStatus]
    ) -> Sequence[WorkflowRunStatus]:
        if not states:
            raise ValueError("prune_states must not be empty")
        for state in states:
            if not isinstance(state, WorkflowRunStatus):
                raise TypeError(f"Invalid status: {state!r}, must be a WorkflowRunStatus")
            if state not in WORKFLOW_TERMINAL_STATUSES:
                raise ValueError(
                    f"Only terminal workflow statuses can be pruned; {state.value} is non-terminal"
                )
        return tuple(states)


class DeletedRecordsSummary(BaseModel):
    """Counters of deleted (or estimated) records per relational persistence table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workflow_runs: int = Field(default=0, ge=0)
    task_runs: int = Field(default=0, ge=0)
    task_attempts: int = Field(default=0, ge=0)
    events: int = Field(default=0, ge=0)
    checkpoints: int = Field(default=0, ge=0)
    external_refs: int = Field(default=0, ge=0)
    manifests: int = Field(default=0, ge=0)

    def to_dict(self) -> dict[str, int]:
        return {
            "workflow_runs": self.workflow_runs,
            "task_runs": self.task_runs,
            "task_attempts": self.task_attempts,
            "events": self.events,
            "checkpoints": self.checkpoints,
            "external_refs": self.external_refs,
            "manifests": self.manifests,
        }


class PruneReport(BaseModel):
    """Structured report returned after retention simulation or real batch pruning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dry_run: bool
    scanned_workflows: int = Field(ge=0)
    eligible_runs_to_prune: int = Field(ge=0)
    deleted_records: DeletedRecordsSummary

    @property
    def estimated_deleted_records(self) -> DeletedRecordsSummary:
        return self.deleted_records

    def to_dict(self) -> dict[str, Any]:
        records_key = "estimated_deleted_records" if self.dry_run else "deleted_records"
        return {
            "dry_run": self.dry_run,
            "scanned_workflows": self.scanned_workflows,
            "eligible_runs_to_prune": self.eligible_runs_to_prune,
            records_key: self.deleted_records.to_dict(),
        }


__all__ = [
    "DEFAULT_PRUNE_STATES",
    "DeletedRecordsSummary",
    "PruneReport",
    "RetentionPolicy",
]
