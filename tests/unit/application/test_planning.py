"""Tests for dependency-graph validation, planning, and runtime readiness."""

from datetime import UTC, datetime

import pytest

from pyworkflowkit.application.planning import (
    DAGValidator,
    ExecutionGroup,
    ExecutionPlan,
    ExecutionPlanner,
    PlannedTask,
    ReadyTaskResolver,
    build_dependency_graph,
)
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import TaskRunStatus
from pyworkflowkit.domain.graph import DependencyGraph, GraphEdge, GraphNode
from pyworkflowkit.domain.ids import TaskId, TaskRunId, WorkflowId, WorkflowRunId
from pyworkflowkit.domain.runtime import TaskRun
from pyworkflowkit.errors import (
    CycleDetectedError,
    DuplicateDependencyError,
    InvalidExecutionPlanError,
    PlanningInvariantError,
    SelfDependencyError,
    UnknownDependencyError,
)

FINISHED_AT = datetime(2026, 9, 25, tzinfo=UTC)


def task(task_id: str, *depends_on: str) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(task_id),
        depends_on=tuple(TaskId(value) for value in depends_on),
    )


def workflow(*tasks: TaskDefinition) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("workflow"),
        version="1",
        tasks=tasks,
    )


def node(task_id: str) -> GraphNode:
    return GraphNode(task_id=TaskId(task_id))


def edge(upstream: str, downstream: str) -> GraphEdge:
    return GraphEdge(
        upstream_task_id=TaskId(upstream),
        downstream_task_id=TaskId(downstream),
    )


def task_run(task_id: str, status: TaskRunStatus = TaskRunStatus.PENDING) -> TaskRun:
    kwargs: dict[str, object] = {}
    if status in {
        TaskRunStatus.SUCCEEDED,
        TaskRunStatus.FAILED,
        TaskRunStatus.CANCELLED,
    }:
        kwargs["finished_at"] = FINISHED_AT

    return TaskRun(
        task_run_id=TaskRunId(f"run-{task_id}"),
        run_id=WorkflowRunId("workflow-run"),
        task_id=TaskId(task_id),
        status=status,
        **kwargs,  # type: ignore[arg-type]
    )


def test_build_dependency_graph_uses_dependency_to_task_edge_direction() -> None:
    definition = workflow(
        task("transform", "fetch", "validate"),
        task("validate", "fetch"),
        task("fetch"),
    )

    graph = build_dependency_graph(definition)

    assert graph.task_ids == (
        TaskId("fetch"),
        TaskId("transform"),
        TaskId("validate"),
    )
    assert graph.edges == (
        edge("fetch", "transform"),
        edge("fetch", "validate"),
        edge("validate", "transform"),
    )


@pytest.mark.parametrize(
    "definition",
    [
        workflow(task("A")),
        workflow(task("A"), task("B", "A"), task("C", "B")),
        workflow(task("A"), task("B", "A"), task("C", "A"), task("D", "B", "C")),
        workflow(task("A"), task("B", "A"), task("C"), task("D", "C")),
    ],
)
def test_dag_validator_accepts_valid_graphs(
    definition: WorkflowDefinition,
) -> None:
    graph = build_dependency_graph(definition)

    DAGValidator().validate(definition, graph)


def test_dag_validator_rejects_unknown_dependency() -> None:
    definition = workflow(task("transform", "missing-fetch"))
    graph = build_dependency_graph(definition)

    with pytest.raises(UnknownDependencyError) as exc_info:
        DAGValidator().validate(definition, graph)

    assert exc_info.value.task_id == TaskId("transform")
    assert exc_info.value.dependency_id == TaskId("missing-fetch")


def test_dag_validator_rejects_unknown_downstream_endpoint() -> None:
    definition = workflow(task("A"))
    graph = DependencyGraph(
        nodes=(node("A"),),
        edges=(edge("A", "missing"),),
    )

    with pytest.raises(UnknownDependencyError):
        DAGValidator().validate(definition, graph)


def test_dag_validator_rejects_self_dependency_defensively() -> None:
    definition = workflow(task("A"))
    graph = DependencyGraph(
        nodes=(node("A"),),
        edges=(edge("A", "A"),),
    )

    with pytest.raises(SelfDependencyError) as exc_info:
        DAGValidator().validate(definition, graph)

    assert exc_info.value.task_id == TaskId("A")


def test_dag_validator_rejects_duplicate_edges_defensively() -> None:
    definition = workflow(task("A"), task("B"))
    graph = DependencyGraph(
        nodes=(node("A"), node("B")),
        edges=(edge("A", "B"), edge("A", "B")),
    )

    with pytest.raises(DuplicateDependencyError) as exc_info:
        DAGValidator().validate(definition, graph)

    assert exc_info.value.task_id == TaskId("B")
    assert exc_info.value.dependency_id == TaskId("A")


def test_dag_validator_rejects_cycle_and_reports_remaining_tasks() -> None:
    definition = workflow(task("A"), task("B"), task("C"))
    graph = DependencyGraph(
        nodes=(node("A"), node("B"), node("C")),
        edges=(edge("A", "B"), edge("B", "C"), edge("C", "A")),
    )

    with pytest.raises(CycleDetectedError) as exc_info:
        DAGValidator().validate(definition, graph)

    assert exc_info.value.task_ids == (
        TaskId("A"),
        TaskId("B"),
        TaskId("C"),
    )


def test_dag_validator_detects_cycle_in_one_disconnected_component() -> None:
    definition = workflow(task("A"), task("B"), task("C"), task("D"))
    graph = DependencyGraph(
        nodes=(node("A"), node("B"), node("C"), node("D")),
        edges=(edge("A", "B"), edge("C", "D"), edge("D", "C")),
    )

    with pytest.raises(CycleDetectedError) as exc_info:
        DAGValidator().validate(definition, graph)

    assert exc_info.value.task_ids == (TaskId("C"), TaskId("D"))


def test_planned_task_rejects_negative_position() -> None:
    with pytest.raises(ValueError, match="position"):
        PlannedTask(task_id=TaskId("A"), position=-1, group_index=0)


def test_execution_group_rejects_empty_group() -> None:
    with pytest.raises(InvalidExecutionPlanError, match="must not be empty"):
        ExecutionGroup(index=0, task_ids=())


def test_execution_group_rejects_duplicate_tasks() -> None:
    with pytest.raises(InvalidExecutionPlanError, match="duplicate"):
        ExecutionGroup(index=0, task_ids=(TaskId("A"), TaskId("A")))


def test_execution_plan_rejects_non_contiguous_positions() -> None:
    with pytest.raises(InvalidExecutionPlanError, match="positions"):
        ExecutionPlan(
            workflow_id=WorkflowId("workflow"),
            workflow_version="1",
            tasks=(PlannedTask(task_id=TaskId("A"), position=1, group_index=0),),
            groups=(ExecutionGroup(index=0, task_ids=(TaskId("A"),)),),
        )


def test_execution_plan_group_for_returns_matching_group() -> None:
    plan = ExecutionPlan(
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
        tasks=(
            PlannedTask(task_id=TaskId("A"), position=0, group_index=0),
            PlannedTask(task_id=TaskId("B"), position=1, group_index=1),
        ),
        groups=(
            ExecutionGroup(index=0, task_ids=(TaskId("A"),)),
            ExecutionGroup(index=1, task_ids=(TaskId("B"),)),
        ),
    )

    assert plan.task_ids == (TaskId("A"), TaskId("B"))
    assert plan.group_for(TaskId("B")).index == 1


def test_execution_plan_group_for_rejects_unknown_task() -> None:
    plan = ExecutionPlan(
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
        tasks=(PlannedTask(task_id=TaskId("A"), position=0, group_index=0),),
        groups=(ExecutionGroup(index=0, task_ids=(TaskId("A"),)),),
    )

    with pytest.raises(KeyError, match="not present"):
        plan.group_for(TaskId("missing"))


def test_execution_planner_builds_single_task_plan() -> None:
    definition = workflow(task("A"))
    graph = build_dependency_graph(definition)
    DAGValidator().validate(definition, graph)

    plan = ExecutionPlanner().build_plan(definition, graph)

    assert plan.task_ids == (TaskId("A"),)
    assert plan.groups == (ExecutionGroup(index=0, task_ids=(TaskId("A"),)),)


def test_execution_planner_builds_linear_groups() -> None:
    definition = workflow(task("C", "B"), task("A"), task("B", "A"))
    graph = build_dependency_graph(definition)
    DAGValidator().validate(definition, graph)

    plan = ExecutionPlanner().build_plan(definition, graph)

    assert tuple(group.task_ids for group in plan.groups) == (
        (TaskId("A"),),
        (TaskId("B"),),
        (TaskId("C"),),
    )
    assert plan.task_ids == (TaskId("A"), TaskId("B"), TaskId("C"))


def test_execution_planner_builds_diamond_groups() -> None:
    definition = workflow(
        task("D", "B", "C"),
        task("C", "A"),
        task("B", "A"),
        task("A"),
    )
    graph = build_dependency_graph(definition)
    DAGValidator().validate(definition, graph)

    plan = ExecutionPlanner().build_plan(definition, graph)

    assert tuple(group.task_ids for group in plan.groups) == (
        (TaskId("A"),),
        (TaskId("B"), TaskId("C")),
        (TaskId("D"),),
    )
    assert tuple(task.position for task in plan.tasks) == (0, 1, 2, 3)
    assert tuple(task.group_index for task in plan.tasks) == (0, 1, 1, 2)


def test_execution_planner_builds_deterministic_disconnected_groups() -> None:
    definition = workflow(
        task("D", "C"),
        task("B", "A"),
        task("C"),
        task("A"),
    )
    graph = build_dependency_graph(definition)
    DAGValidator().validate(definition, graph)

    plan = ExecutionPlanner().build_plan(definition, graph)

    assert tuple(group.task_ids for group in plan.groups) == (
        (TaskId("A"), TaskId("C")),
        (TaskId("B"), TaskId("D")),
    )


def test_execution_planner_is_independent_of_definition_input_order() -> None:
    first = workflow(
        task("A"),
        task("B", "A"),
        task("C", "A"),
        task("D", "B", "C"),
    )
    second = workflow(
        task("D", "B", "C"),
        task("C", "A"),
        task("B", "A"),
        task("A"),
    )

    first_graph = build_dependency_graph(first)
    second_graph = build_dependency_graph(second)

    first_plan = ExecutionPlanner().build_plan(first, first_graph)
    second_plan = ExecutionPlanner().build_plan(second, second_graph)

    assert first_plan.task_ids == second_plan.task_ids
    assert first_plan.groups == second_plan.groups


def test_execution_planner_rejects_graph_with_different_task_set() -> None:
    definition = workflow(task("A"), task("B"))
    graph = DependencyGraph(nodes=(node("A"),), edges=())

    with pytest.raises(PlanningInvariantError, match="different tasks"):
        ExecutionPlanner().build_plan(definition, graph)


def test_execution_planner_defensively_rejects_cycle() -> None:
    definition = workflow(task("A"), task("B"))
    graph = DependencyGraph(
        nodes=(node("A"), node("B")),
        edges=(edge("A", "B"), edge("B", "A")),
    )

    with pytest.raises(PlanningInvariantError, match="remaining tasks"):
        ExecutionPlanner().build_plan(definition, graph)


def test_ready_resolver_marks_root_pending_task_ready() -> None:
    definition = workflow(task("A"), task("B", "A"))
    graph = build_dependency_graph(definition)
    runs = {
        TaskId("A"): task_run("A"),
        TaskId("B"): task_run("B"),
    }

    assert ReadyTaskResolver().is_ready(
        task_run=runs[TaskId("A")],
        graph=graph,
        task_runs_by_task_id=runs,
    )


def test_ready_resolver_requires_all_fan_in_dependencies_to_succeed() -> None:
    definition = workflow(
        task("A"),
        task("B", "A"),
        task("C", "A"),
        task("D", "B", "C"),
    )
    graph = build_dependency_graph(definition)
    runs = {
        TaskId("A"): task_run("A", TaskRunStatus.SUCCEEDED),
        TaskId("B"): task_run("B", TaskRunStatus.SUCCEEDED),
        TaskId("C"): task_run("C"),
        TaskId("D"): task_run("D"),
    }

    resolver = ReadyTaskResolver()
    assert not resolver.is_ready(
        task_run=runs[TaskId("D")],
        graph=graph,
        task_runs_by_task_id=runs,
    )

    runs[TaskId("C")] = task_run("C", TaskRunStatus.SUCCEEDED)

    assert resolver.is_ready(
        task_run=runs[TaskId("D")],
        graph=graph,
        task_runs_by_task_id=runs,
    )


@pytest.mark.parametrize(
    "status",
    [
        TaskRunStatus.READY,
        TaskRunStatus.RUNNING,
        TaskRunStatus.SUCCEEDED,
        TaskRunStatus.FAILED,
        TaskRunStatus.CANCELLED,
    ],
)
def test_ready_resolver_only_considers_pending_task_runs(
    status: TaskRunStatus,
) -> None:
    definition = workflow(task("A"))
    graph = build_dependency_graph(definition)
    run = task_run("A", status)

    assert not ReadyTaskResolver().is_ready(
        task_run=run,
        graph=graph,
        task_runs_by_task_id={TaskId("A"): run},
    )


def test_ready_resolver_find_ready_returns_stable_graph_order() -> None:
    definition = workflow(task("C"), task("A"), task("B"))
    graph = build_dependency_graph(definition)
    runs = {
        TaskId("C"): task_run("C"),
        TaskId("B"): task_run("B"),
        TaskId("A"): task_run("A"),
    }

    ready = ReadyTaskResolver().find_ready(
        graph=graph,
        task_runs_by_task_id=runs,
    )

    assert tuple(run.task_id for run in ready) == (
        TaskId("A"),
        TaskId("B"),
        TaskId("C"),
    )


def test_ready_resolver_rejects_missing_upstream_task_run() -> None:
    definition = workflow(task("A"), task("B", "A"))
    graph = build_dependency_graph(definition)
    downstream = task_run("B")

    with pytest.raises(PlanningInvariantError, match="upstream"):
        ReadyTaskResolver().is_ready(
            task_run=downstream,
            graph=graph,
            task_runs_by_task_id={TaskId("B"): downstream},
        )


def test_ready_resolver_find_ready_rejects_missing_graph_task_run() -> None:
    definition = workflow(task("A"), task("B"))
    graph = build_dependency_graph(definition)

    with pytest.raises(PlanningInvariantError, match="graph task 'B'"):
        ReadyTaskResolver().find_ready(
            graph=graph,
            task_runs_by_task_id={TaskId("A"): task_run("A")},
        )


def test_ready_resolver_rejects_mapping_identity_mismatch() -> None:
    definition = workflow(task("A"))
    graph = build_dependency_graph(definition)

    with pytest.raises(PlanningInvariantError, match="does not match"):
        ReadyTaskResolver().find_ready(
            graph=graph,
            task_runs_by_task_id={TaskId("A"): task_run("B")},
        )


def test_ready_resolver_rejects_task_absent_from_graph() -> None:
    definition = workflow(task("A"))
    graph = build_dependency_graph(definition)
    run = task_run("B")

    with pytest.raises(PlanningInvariantError, match="absent from graph"):
        ReadyTaskResolver().is_ready(
            task_run=run,
            graph=graph,
            task_runs_by_task_id={TaskId("B"): run},
        )
