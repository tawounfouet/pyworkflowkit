"""Dependency-graph construction and DAG validation services."""

from collections import Counter
from heapq import heapify, heappop, heappush

from pyworkflowkit.domain.definitions import WorkflowDefinition
from pyworkflowkit.domain.graph import DependencyGraph, GraphEdge, GraphNode
from pyworkflowkit.domain.ids import TaskId
from pyworkflowkit.errors import (
    CycleDetectedError,
    DuplicateDependencyError,
    SelfDependencyError,
    UnknownDependencyError,
)


def build_dependency_graph(workflow: WorkflowDefinition) -> DependencyGraph:
    """Build a structural dependency graph from a workflow definition."""
    nodes = tuple(GraphNode(task_id=task.task_id) for task in workflow.tasks)
    edges = tuple(
        GraphEdge(
            upstream_task_id=dependency_id,
            downstream_task_id=task.task_id,
        )
        for task in workflow.tasks
        for dependency_id in task.depends_on
    )
    return DependencyGraph(nodes=nodes, edges=edges)


class DAGValidator:
    """Validate that a DependencyGraph is a well-formed DAG."""

    def validate(
        self,
        workflow: WorkflowDefinition,
        graph: DependencyGraph,
    ) -> None:
        known_task_ids = frozenset(task.task_id for task in workflow.tasks)

        self._validate_unknown_dependencies(graph, known_task_ids)
        self._validate_self_dependencies(graph)
        self._validate_duplicate_edges(graph)
        self._validate_acyclic(graph)

    @staticmethod
    def _validate_unknown_dependencies(
        graph: DependencyGraph,
        known_task_ids: frozenset[TaskId],
    ) -> None:
        for edge in graph.edges:
            if edge.upstream_task_id not in known_task_ids:
                raise UnknownDependencyError(
                    task_id=edge.downstream_task_id,
                    dependency_id=edge.upstream_task_id,
                )
            if edge.downstream_task_id not in known_task_ids:
                raise UnknownDependencyError(
                    task_id=edge.downstream_task_id,
                    dependency_id=edge.upstream_task_id,
                )

    @staticmethod
    def _validate_self_dependencies(graph: DependencyGraph) -> None:
        for edge in graph.edges:
            if edge.upstream_task_id == edge.downstream_task_id:
                raise SelfDependencyError(task_id=edge.upstream_task_id)

    @staticmethod
    def _validate_duplicate_edges(graph: DependencyGraph) -> None:
        edge_counts = Counter(
            (edge.upstream_task_id, edge.downstream_task_id) for edge in graph.edges
        )
        for (upstream_task_id, downstream_task_id), count in edge_counts.items():
            if count > 1:
                raise DuplicateDependencyError(
                    task_id=downstream_task_id,
                    dependency_id=upstream_task_id,
                )

    @staticmethod
    def _validate_acyclic(graph: DependencyGraph) -> None:
        in_degree = {task_id: graph.in_degree(task_id) for task_id in graph.task_ids}
        ready = [task_id for task_id, degree in in_degree.items() if degree == 0]
        heapify(ready)

        processed: list[TaskId] = []
        while ready:
            task_id = heappop(ready)
            processed.append(task_id)

            for downstream_task_id in graph.downstream_of(task_id):
                in_degree[downstream_task_id] -= 1
                if in_degree[downstream_task_id] == 0:
                    heappush(ready, downstream_task_id)

        if len(processed) != len(graph.task_ids):
            remaining = tuple(
                sorted(
                    (task_id for task_id in graph.task_ids if in_degree[task_id] > 0),
                    key=str,
                )
            )
            raise CycleDetectedError(task_ids=remaining)


__all__ = ["DAGValidator", "build_dependency_graph"]
