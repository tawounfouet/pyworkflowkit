"""Runtime inspection and deadlock diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from pyworkflowkit.domain.definitions import WorkflowDefinition
from pyworkflowkit.domain.enums import TASK_TERMINAL_STATUSES, TaskRunStatus
from pyworkflowkit.domain.ids import TaskId, WorkflowRunId
from pyworkflowkit.ports.metadata_store import MetadataStore


@dataclass(frozen=True, slots=True)
class TaskInspection:
    task_id: str
    task_run_id: str
    status: str
    attempt_count: int
    upstream_task_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeInspection:
    run_id: str
    workflow_id: str
    workflow_version: str
    status: str
    tasks: tuple[TaskInspection, ...]
    event_count: int
    ready_task_ids: tuple[str, ...]
    blocked_task_ids: tuple[str, ...]
    deadlocked: bool
    deadlock_reason: str | None = None


class RuntimeInspector:
    """Build a diagnostic snapshot from persisted runtime state."""

    def __init__(self, *, metadata_store: MetadataStore) -> None:
        self._metadata_store = metadata_store

    def inspect(
        self,
        *,
        workflow: WorkflowDefinition,
        run_id: WorkflowRunId,
    ) -> RuntimeInspection:
        run = self._metadata_store.get_workflow_run(run_id)
        if run.workflow_id != workflow.workflow_id or run.workflow_version != workflow.version:
            raise ValueError("workflow definition does not match persisted run identity")

        definitions = {task.task_id: task for task in workflow.tasks}
        task_runs = tuple(self._metadata_store.list_task_runs(run_id))
        by_task_id = {task_run.task_id: task_run for task_run in task_runs}

        missing = tuple(
            sorted(
                (task_id for task_id in definitions if task_id not in by_task_id),
                key=str,
            )
        )
        if missing:
            rendered = ", ".join(str(task_id) for task_id in missing)
            raise ValueError(f"runtime inspection is missing TaskRun values for: {rendered}")

        ready: list[TaskId] = []
        blocked: list[TaskId] = []
        inspections: list[TaskInspection] = []

        for task_id in sorted(definitions, key=str):
            definition = definitions[task_id]
            task_run = by_task_id[task_id]
            upstream_ids = tuple(sorted(definition.depends_on, key=str))
            if task_run.status not in TASK_TERMINAL_STATUSES:
                dependencies_succeeded = all(
                    by_task_id[upstream_id].status is TaskRunStatus.SUCCEEDED
                    for upstream_id in upstream_ids
                )
                if dependencies_succeeded:
                    ready.append(task_id)
                else:
                    blocked.append(task_id)

            inspections.append(
                TaskInspection(
                    task_id=str(task_id),
                    task_run_id=str(task_run.task_run_id),
                    status=task_run.status.value,
                    attempt_count=len(
                        self._metadata_store.list_task_attempts(task_run.task_run_id)
                    ),
                    upstream_task_ids=tuple(str(value) for value in upstream_ids),
                )
            )

        nonterminal = [
            task_run for task_run in task_runs if task_run.status not in TASK_TERMINAL_STATUSES
        ]
        deadlocked = bool(nonterminal) and not ready
        reason = None
        if deadlocked:
            reason = (
                "non-terminal tasks remain but none has all dependencies in SUCCEEDED state"
            )

        return RuntimeInspection(
            run_id=str(run.run_id),
            workflow_id=str(run.workflow_id),
            workflow_version=run.workflow_version,
            status=run.status.value,
            tasks=tuple(inspections),
            event_count=len(self._metadata_store.list_events(run_id)),
            ready_task_ids=tuple(str(value) for value in ready),
            blocked_task_ids=tuple(str(value) for value in blocked),
            deadlocked=deadlocked,
            deadlock_reason=reason,
        )


__all__ = ["RuntimeInspection", "RuntimeInspector", "TaskInspection"]
