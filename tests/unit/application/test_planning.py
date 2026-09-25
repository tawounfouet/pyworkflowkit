"""Tests for dependency-graph construction and DAG validation."""

import pytest

from pyworkflowkit.application.planning import DAGValidator, build_dependency_graph
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.graph import DependencyGraph, GraphEdge, GraphNode
from pyworkflowkit.domain.ids import TaskId, WorkflowId
from pyworkflowkit.errors import (
    CycleDetectedError,
    DuplicateDependencyError,
    SelfDependencyError,
    UnknownDependencyError,
)


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
