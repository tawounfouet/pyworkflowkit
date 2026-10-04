"""Topological task classification and checkpoint resolution for selective resume."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pyworkflowkit.errors import MetadataNotFoundError
from pyworkflowkit.persistence import MetadataStore
from pyworkflowkit.planning import ExecutionPlan
from pyworkflowkit.runtime.entities import TaskRun
from pyworkflowkit.runtime.evidence import TaskOutputCheckpoint
from pyworkflowkit.states import TaskRunStatus


@dataclass(frozen=True, slots=True)
class TaskResumeClassification:
    """Classified task partition and preloaded checkpoints for a resume run."""

    reused_keys: frozenset[str]
    reused_checkpoints: Mapping[str, TaskOutputCheckpoint]
    initial_outputs: Mapping[str, object]


def classify_tasks_for_resume(
    *,
    plan: ExecutionPlan,
    parent_task_runs: Mapping[str, TaskRun],
    metadata: MetadataStore,
    force_recompute_tasks: Sequence[str] | None = None,
) -> TaskResumeClassification:
    """Classify tasks into REUSED and to-be-executed according to deterministic resume rules."""
    force_set = set(force_recompute_tasks or ())
    reused_keys: set[str] = set()
    reused_checkpoints: dict[str, TaskOutputCheckpoint] = {}
    initial_outputs: dict[str, object] = {}

    for entry in plan.tasks:
        if entry.key in force_set:
            continue

        if not entry.task.is_deterministic:
            continue

        parent_task_run = parent_task_runs.get(entry.key)
        if parent_task_run is None:
            continue

        if parent_task_run.status not in {TaskRunStatus.SUCCEEDED, TaskRunStatus.REUSED}:
            continue

        if not all(dep in reused_keys for dep in entry.dependencies):
            continue

        try:
            checkpoint = metadata.get_task_output_checkpoint(parent_task_run.task_run_id)
        except MetadataNotFoundError:
            continue

        reused_keys.add(entry.key)
        reused_checkpoints[entry.key] = checkpoint
        initial_outputs[entry.key] = checkpoint.output

    return TaskResumeClassification(
        reused_keys=frozenset(reused_keys),
        reused_checkpoints=reused_checkpoints,
        initial_outputs=initial_outputs,
    )


__all__ = ["TaskResumeClassification", "classify_tasks_for_resume"]
