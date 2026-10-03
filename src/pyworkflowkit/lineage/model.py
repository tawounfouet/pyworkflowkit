"""Canonical V2 manifest and execution-lineage values."""

from __future__ import annotations

from dataclasses import dataclass

from pyworkflowkit.runtime.evidence import JsonValue, RuntimeEvent
from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId
from pyworkflowkit.runtime.references import ExternalRunRef
from pyworkflowkit.states import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus


@dataclass(frozen=True, slots=True)
class ManifestAttempt:
    attempt_id: TaskAttemptId
    attempt_number: int
    status: TaskAttemptStatus


@dataclass(frozen=True, slots=True)
class ManifestTaskRun:
    task_run_id: TaskRunId
    task_key: str
    status: TaskRunStatus
    attempts: tuple[ManifestAttempt, ...]
    external_runs: tuple[ExternalRunRef, ...]
    output: JsonValue | None = None
    output_digest: str | None = None
    output_recorded_at: str | None = None


@dataclass(frozen=True, slots=True)
class RunManifest:
    """Deterministic durable-evidence projection for one WorkflowRun."""

    schema_version: str
    workflow_run_id: WorkflowRunId
    workflow_name: str
    workflow_version: str
    definition_fingerprint: str
    plan_fingerprint: str
    status: WorkflowRunStatus
    created_at: str
    started_at: str | None
    ended_at: str | None
    tasks: tuple[ManifestTaskRun, ...]
    events: tuple[RuntimeEvent, ...]


@dataclass(frozen=True, slots=True)
class LineageDependency:
    upstream_task_run_id: TaskRunId
    downstream_task_run_id: TaskRunId


@dataclass(frozen=True, slots=True)
class TaskExecutionLineage:
    task_key: str
    task_run_id: TaskRunId
    attempt_ids: tuple[TaskAttemptId, ...]
    external_runs: tuple[ExternalRunRef, ...]
    output_digest: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionLineage:
    """Deterministic execution provenance for one persisted workflow run."""

    workflow_run_id: WorkflowRunId
    workflow_name: str
    workflow_version: str
    definition_fingerprint: str
    plan_fingerprint: str
    tasks: tuple[TaskExecutionLineage, ...]
    dependencies: tuple[LineageDependency, ...]


__all__ = [
    "ExecutionLineage",
    "LineageDependency",
    "ManifestAttempt",
    "ManifestTaskRun",
    "RunManifest",
    "TaskExecutionLineage",
]
