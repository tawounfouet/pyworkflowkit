"""Canonical V2 runtime inspection over plan plus durable evidence."""

from __future__ import annotations

from dataclasses import dataclass

from pyworkflowkit.authoring import WorkflowDefinition
from pyworkflowkit.errors import MetadataNotFoundError, RuntimeInvariantError
from pyworkflowkit.persistence import MetadataStore
from pyworkflowkit.planning import ExecutionPlan, WorkflowPlanner
from pyworkflowkit.runtime.identity import TaskRunId, WorkflowRunId
from pyworkflowkit.states import TaskRunStatus
from pyworkflowkit.states.enums import TASK_RUN_TERMINAL_STATUSES

_SCHEDULABLE_TASK_STATUSES = frozenset(
    {
        TaskRunStatus.PENDING,
        TaskRunStatus.READY,
    }
)
_ACTIVE_TASK_STATUSES = frozenset(
    {
        TaskRunStatus.RUNNING,
        TaskRunStatus.UNKNOWN_OUTCOME,
    }
)


@dataclass(frozen=True, slots=True)
class TaskInspection:
    task_key: str
    task_run_id: TaskRunId
    status: TaskRunStatus
    attempt_count: int
    upstream_task_keys: tuple[str, ...]
    external_run_count: int
    output_checkpointed: bool


@dataclass(frozen=True, slots=True)
class RuntimeInspection:
    workflow_run_id: WorkflowRunId
    workflow_name: str
    workflow_version: str
    status: str
    tasks: tuple[TaskInspection, ...]
    event_count: int
    output_checkpoint_count: int
    ready_task_keys: tuple[str, ...]
    blocked_task_keys: tuple[str, ...]
    deadlocked: bool
    deadlock_reason: str | None = None


class RuntimeInspector:
    """Build a deterministic V2 diagnostic snapshot without mutating runtime state."""

    def __init__(
        self,
        *,
        metadata: MetadataStore,
        planner: WorkflowPlanner | None = None,
    ) -> None:
        if not isinstance(metadata, MetadataStore):
            raise TypeError("metadata must satisfy the V2 MetadataStore Protocol")
        self._metadata = metadata
        self._planner = planner or WorkflowPlanner()

    def inspect(
        self,
        workflow: WorkflowDefinition | ExecutionPlan,
        workflow_run_id: WorkflowRunId,
    ) -> RuntimeInspection:
        plan = (
            self._planner.compile(workflow)
            if isinstance(workflow, WorkflowDefinition)
            else workflow
        )
        if not isinstance(plan, ExecutionPlan):
            raise TypeError("workflow must be WorkflowDefinition or ExecutionPlan")

        run = self._metadata.get_workflow_run(workflow_run_id)
        if (
            run.workflow_name != plan.workflow_name
            or run.workflow_version != plan.workflow_version
            or run.definition_fingerprint != plan.definition_fingerprint
            or run.plan_fingerprint != plan.fingerprint()
        ):
            raise RuntimeInvariantError(
                reason="runtime inspection plan does not match persisted WorkflowRun identity"
            )

        task_runs = tuple(self._metadata.list_task_runs(workflow_run_id))
        by_key = {task_run.task_key: task_run for task_run in task_runs}
        ready: list[str] = []
        blocked: list[str] = []
        inspections: list[TaskInspection] = []
        checkpoint_count = 0

        for entry in plan.tasks:
            task_run = by_key.get(entry.key)
            if task_run is None:
                raise RuntimeInvariantError(
                    reason=f"runtime inspection is missing TaskRun for {entry.key!r}"
                )
            attempts = tuple(self._metadata.list_task_attempts(task_run.task_run_id))
            external_count = sum(
                len(self._metadata.list_external_run_refs(attempt.attempt_id))
                for attempt in attempts
            )
            try:
                self._metadata.get_task_output_checkpoint(task_run.task_run_id)
            except MetadataNotFoundError:
                checkpointed = False
            else:
                checkpointed = True
                checkpoint_count += 1

            if task_run.status is TaskRunStatus.BLOCKED:
                blocked.append(entry.key)
            elif task_run.status in _SCHEDULABLE_TASK_STATUSES:
                dependencies_succeeded = all(
                    by_key[upstream].status is TaskRunStatus.SUCCEEDED
                    for upstream in entry.dependencies
                )
                if dependencies_succeeded:
                    ready.append(entry.key)
                else:
                    blocked.append(entry.key)

            inspections.append(
                TaskInspection(
                    task_key=entry.key,
                    task_run_id=task_run.task_run_id,
                    status=task_run.status,
                    attempt_count=len(attempts),
                    upstream_task_keys=tuple(entry.dependencies),
                    external_run_count=external_count,
                    output_checkpointed=checkpointed,
                )
            )

        nonterminal = [
            task_run for task_run in task_runs if task_run.status not in TASK_RUN_TERMINAL_STATUSES
        ]
        has_active_work = any(task_run.status in _ACTIVE_TASK_STATUSES for task_run in nonterminal)
        deadlocked = bool(nonterminal) and not ready and not has_active_work
        reason = (
            "non-terminal tasks remain but no task has all dependencies in SUCCEEDED state"
            if deadlocked
            else None
        )
        return RuntimeInspection(
            workflow_run_id=run.run_id,
            workflow_name=run.workflow_name,
            workflow_version=run.workflow_version,
            status=run.status.value,
            tasks=tuple(inspections),
            event_count=len(self._metadata.list_runtime_events(workflow_run_id)),
            output_checkpoint_count=checkpoint_count,
            ready_task_keys=tuple(ready),
            blocked_task_keys=tuple(blocked),
            deadlocked=deadlocked,
            deadlock_reason=reason,
        )


__all__ = ["RuntimeInspection", "RuntimeInspector", "TaskInspection"]
