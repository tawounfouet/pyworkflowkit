"""Tests for deterministic FAIL_FAST failure propagation."""

from datetime import UTC, datetime

from pyworkflowkit.application.failure import FailurePropagator, TaskSkipDecision
from pyworkflowkit.application.planning import build_dependency_graph
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import SkipReason, TaskRunStatus
from pyworkflowkit.domain.ids import TaskId, TaskRunId, WorkflowId, WorkflowRunId
from pyworkflowkit.domain.runtime import TaskRun

NOW = datetime(2026, 9, 25, 21, 0, tzinfo=UTC)


def definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("workflow"),
        version="1",
        tasks=(
            TaskDefinition(task_id=TaskId("A")),
            TaskDefinition(task_id=TaskId("B"), depends_on=(TaskId("A"),)),
            TaskDefinition(task_id=TaskId("C")),
            TaskDefinition(task_id=TaskId("D"), depends_on=(TaskId("B"),)),
        ),
    )


def task_run(task_id: str, status: TaskRunStatus = TaskRunStatus.PENDING) -> TaskRun:
    kwargs: dict[str, object] = {}
    if status is TaskRunStatus.RUNNING:
        kwargs["started_at"] = NOW
    elif status is TaskRunStatus.SUCCEEDED:
        kwargs["started_at"] = NOW
        kwargs["finished_at"] = NOW

    return TaskRun(
        task_run_id=TaskRunId(f"run:{task_id}"),
        run_id=WorkflowRunId("run"),
        task_id=TaskId(task_id),
        status=status,
        **kwargs,  # type: ignore[arg-type]
    )


def test_fail_fast_classifies_descendants_and_independent_tasks() -> None:
    workflow = definition()
    graph = build_dependency_graph(workflow)
    runs = {
        TaskId("A"): task_run("A", TaskRunStatus.RUNNING),
        TaskId("B"): task_run("B"),
        TaskId("C"): task_run("C"),
        TaskId("D"): task_run("D"),
    }

    decisions = FailurePropagator().plan_fail_fast(
        failed_task_id=TaskId("A"),
        graph=graph,
        task_runs_by_task_id=runs,
        plan_task_ids=(TaskId("A"), TaskId("C"), TaskId("B"), TaskId("D")),
    )

    assert decisions == (
        TaskSkipDecision(
            task_id=TaskId("C"),
            reason=SkipReason.FAIL_FAST_ABORT,
        ),
        TaskSkipDecision(
            task_id=TaskId("B"),
            reason=SkipReason.DEPENDENCY_FAILED,
        ),
        TaskSkipDecision(
            task_id=TaskId("D"),
            reason=SkipReason.DEPENDENCY_FAILED,
        ),
    )


def test_fail_fast_does_not_reclassify_already_terminal_tasks() -> None:
    workflow = definition()
    graph = build_dependency_graph(workflow)
    runs = {
        TaskId("A"): task_run("A", TaskRunStatus.RUNNING),
        TaskId("B"): task_run("B"),
        TaskId("C"): task_run("C", TaskRunStatus.SUCCEEDED),
        TaskId("D"): task_run("D"),
    }

    decisions = FailurePropagator().plan_fail_fast(
        failed_task_id=TaskId("A"),
        graph=graph,
        task_runs_by_task_id=runs,
        plan_task_ids=(TaskId("A"), TaskId("C"), TaskId("B"), TaskId("D")),
    )

    assert tuple(decision.task_id for decision in decisions) == (
        TaskId("B"),
        TaskId("D"),
    )
