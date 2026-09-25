"""Tests for immutable dependency-graph structures."""

import pytest

from pyworkflowkit.domain.graph import DependencyGraph, GraphEdge, GraphNode
from pyworkflowkit.domain.ids import TaskId


def node(task_id: str) -> GraphNode:
    return GraphNode(task_id=TaskId(task_id))


def edge(upstream: str, downstream: str) -> GraphEdge:
    return GraphEdge(
        upstream_task_id=TaskId(upstream),
        downstream_task_id=TaskId(downstream),
    )


def test_graph_node_rejects_blank_task_id() -> None:
    with pytest.raises(ValueError, match="task_id"):
        node(" ")


@pytest.mark.parametrize(
    ("upstream", "downstream", "field_name"),
    [
        ("", "B", "upstream_task_id"),
        ("A", " ", "downstream_task_id"),
    ],
)
def test_graph_edge_rejects_blank_endpoint(
    upstream: str,
    downstream: str,
    field_name: str,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        edge(upstream, downstream)


def test_dependency_graph_canonicalizes_node_and_edge_order() -> None:
    graph = DependencyGraph(
        nodes=(node("C"), node("A"), node("B")),
        edges=(edge("B", "C"), edge("A", "C"), edge("A", "B")),
    )

    assert graph.task_ids == (TaskId("A"), TaskId("B"), TaskId("C"))
    assert graph.edges == (
        edge("A", "B"),
        edge("A", "C"),
        edge("B", "C"),
    )


def test_dependency_graph_rejects_duplicate_nodes() -> None:
    with pytest.raises(ValueError, match="duplicate task nodes"):
        DependencyGraph(
            nodes=(node("A"), node("A")),
            edges=(),
        )


def test_dependency_graph_exposes_linear_relationships() -> None:
    graph = DependencyGraph(
        nodes=(node("A"), node("B"), node("C")),
        edges=(edge("A", "B"), edge("B", "C")),
    )

    assert graph.upstream_of(TaskId("A")) == ()
    assert graph.upstream_of(TaskId("B")) == (TaskId("A"),)
    assert graph.downstream_of(TaskId("B")) == (TaskId("C"),)
    assert graph.in_degree(TaskId("B")) == 1
    assert graph.out_degree(TaskId("B")) == 1
    assert graph.roots() == (TaskId("A"),)
    assert graph.leaves() == (TaskId("C"),)


def test_dependency_graph_supports_disconnected_components() -> None:
    graph = DependencyGraph(
        nodes=(node("D"), node("B"), node("A"), node("C")),
        edges=(edge("A", "B"), edge("C", "D")),
    )

    assert graph.roots() == (TaskId("A"), TaskId("C"))
    assert graph.leaves() == (TaskId("B"), TaskId("D"))


def test_dependency_graph_preserves_invalid_unknown_edge_for_validation() -> None:
    graph = DependencyGraph(
        nodes=(node("B"),),
        edges=(edge("missing", "B"),),
    )

    assert graph.edges == (edge("missing", "B"),)
    assert graph.upstream_of(TaskId("B")) == (TaskId("missing"),)


@pytest.mark.parametrize(
    "method_name",
    ["upstream_of", "downstream_of", "in_degree", "out_degree"],
)
def test_dependency_graph_rejects_unknown_task_query(method_name: str) -> None:
    graph = DependencyGraph(nodes=(node("A"),), edges=())

    with pytest.raises(KeyError, match="Unknown graph task"):
        getattr(graph, method_name)(TaskId("missing"))


def test_graph_collections_are_read_only_tuples() -> None:
    graph = DependencyGraph(
        nodes=(node("A"), node("B")),
        edges=(edge("A", "B"),),
    )

    assert isinstance(graph.nodes, tuple)
    assert isinstance(graph.edges, tuple)
    assert isinstance(graph.task_ids, tuple)
