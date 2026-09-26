"""Immutable execution-lineage projection values."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LineageDependency:
    """Runtime projection of one declared task dependency."""

    upstream_task_run_id: str
    downstream_task_run_id: str


@dataclass(frozen=True, slots=True)
class TaskExecutionLineage:
    """Runtime evidence attached to one logical task instance."""

    task_id: str
    task_run_id: str
    attempt_ids: tuple[str, ...] = ()
    artifact_ids: tuple[str, ...] = ()
    external_ref_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionLineage:
    """Deterministic execution-provenance projection for one workflow run."""

    run_id: str
    workflow_id: str
    workflow_version: str
    tasks: tuple[TaskExecutionLineage, ...]
    dependencies: tuple[LineageDependency, ...]


__all__ = [
    "ExecutionLineage",
    "LineageDependency",
    "TaskExecutionLineage",
]
