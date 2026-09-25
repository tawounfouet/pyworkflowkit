"""Failure-propagation decisions for FAIL_FAST workflows."""

from collections.abc import Mapping
from dataclasses import dataclass

from pyworkflowkit.domain.enums import SkipReason, TaskRunStatus
from pyworkflowkit.domain.graph import DependencyGraph
from pyworkflowkit.domain.ids import TaskId
from pyworkflowkit.domain.runtime import TaskRun


@dataclass(frozen=True, slots=True)
class TaskSkipDecision:
    """Why one undispatched task must be skipped after terminal failure."""

    task_id: TaskId
    reason: SkipReason


class FailurePropagator:
    """Classify undispatched tasks after a terminal task failure."""

    def plan_fail_fast(
        self,
        *,
        failed_task_id: TaskId,
        graph: DependencyGraph,
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
        plan_task_ids: tuple[TaskId, ...],
    ) -> tuple[TaskSkipDecision, ...]:
        descendants = self._descendants_of(
            graph=graph,
            task_id=failed_task_id,
        )

        decisions: list[TaskSkipDecision] = []
        for task_id in plan_task_ids:
            if task_id == failed_task_id:
                continue

            task_run = task_runs_by_task_id[task_id]
            if task_run.status not in {TaskRunStatus.PENDING, TaskRunStatus.READY}:
                continue

            reason = (
                SkipReason.DEPENDENCY_FAILED
                if task_id in descendants
                else SkipReason.FAIL_FAST_ABORT
            )
            decisions.append(TaskSkipDecision(task_id=task_id, reason=reason))

        return tuple(decisions)

    @staticmethod
    def _descendants_of(
        *,
        graph: DependencyGraph,
        task_id: TaskId,
    ) -> frozenset[TaskId]:
        discovered: set[TaskId] = set()
        pending = list(graph.downstream_of(task_id))

        while pending:
            candidate = pending.pop()
            if candidate in discovered:
                continue
            discovered.add(candidate)
            pending.extend(graph.downstream_of(candidate))

        return frozenset(discovered)


__all__ = ["FailurePropagator", "TaskSkipDecision"]
