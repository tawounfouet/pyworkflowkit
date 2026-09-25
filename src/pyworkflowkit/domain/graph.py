"""Immutable structural graph values for workflow dependencies."""

from collections.abc import Iterable
from dataclasses import dataclass

from pyworkflowkit.domain.ids import TaskId, validate_non_empty_identifier


@dataclass(frozen=True, slots=True)
class GraphNode:
    """One task node in a dependency graph."""

    task_id: TaskId

    def __post_init__(self) -> None:
        validate_non_empty_identifier(str(self.task_id), field_name="task_id")


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """Directed edge from an upstream task to a downstream task."""

    upstream_task_id: TaskId
    downstream_task_id: TaskId

    def __post_init__(self) -> None:
        validate_non_empty_identifier(
            str(self.upstream_task_id),
            field_name="upstream_task_id",
        )
        validate_non_empty_identifier(
            str(self.downstream_task_id),
            field_name="downstream_task_id",
        )


class DependencyGraph:
    """Read-only structural representation of task dependencies.

    Construction does not prove DAG validity. Invalid edges are retained so
    that DAGValidator can report precise graph errors instead of silently
    normalizing them.
    """

    __slots__ = (
        "_downstream_by_id",
        "_edges",
        "_nodes",
        "_nodes_by_id",
        "_upstream_by_id",
    )

    def __init__(
        self,
        *,
        nodes: Iterable[GraphNode],
        edges: Iterable[GraphEdge],
    ) -> None:
        canonical_nodes = tuple(sorted(nodes, key=lambda node: str(node.task_id)))
        node_ids = [node.task_id for node in canonical_nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("DependencyGraph cannot contain duplicate task nodes.")

        canonical_edges = tuple(
            sorted(
                edges,
                key=lambda edge: (
                    str(edge.upstream_task_id),
                    str(edge.downstream_task_id),
                ),
            )
        )

        self._nodes = canonical_nodes
        self._edges = canonical_edges
        self._nodes_by_id = {node.task_id: node for node in canonical_nodes}

        upstream_by_id: dict[TaskId, list[TaskId]] = {
            task_id: [] for task_id in self._nodes_by_id
        }
        downstream_by_id: dict[TaskId, list[TaskId]] = {
            task_id: [] for task_id in self._nodes_by_id
        }

        for edge in canonical_edges:
            if edge.downstream_task_id in upstream_by_id:
                upstream_by_id[edge.downstream_task_id].append(edge.upstream_task_id)
            if edge.upstream_task_id in downstream_by_id:
                downstream_by_id[edge.upstream_task_id].append(edge.downstream_task_id)

        self._upstream_by_id = {
            task_id: tuple(sorted(task_ids, key=str))
            for task_id, task_ids in upstream_by_id.items()
        }
        self._downstream_by_id = {
            task_id: tuple(sorted(task_ids, key=str))
            for task_id, task_ids in downstream_by_id.items()
        }

    @property
    def nodes(self) -> tuple[GraphNode, ...]:
        """Return graph nodes in deterministic TaskId order."""
        return self._nodes

    @property
    def edges(self) -> tuple[GraphEdge, ...]:
        """Return graph edges in deterministic endpoint order."""
        return self._edges

    @property
    def task_ids(self) -> tuple[TaskId, ...]:
        """Return known task identifiers in deterministic order."""
        return tuple(node.task_id for node in self._nodes)

    def upstream_of(self, task_id: TaskId) -> tuple[TaskId, ...]:
        """Return direct upstream dependencies for a known task."""
        self._require_known_task(task_id)
        return self._upstream_by_id[task_id]

    def downstream_of(self, task_id: TaskId) -> tuple[TaskId, ...]:
        """Return direct downstream dependants for a known task."""
        self._require_known_task(task_id)
        return self._downstream_by_id[task_id]

    def in_degree(self, task_id: TaskId) -> int:
        """Return the direct incoming edge count for a known task."""
        return len(self.upstream_of(task_id))

    def out_degree(self, task_id: TaskId) -> int:
        """Return the direct outgoing edge count for a known task."""
        return len(self.downstream_of(task_id))

    def roots(self) -> tuple[TaskId, ...]:
        """Return known tasks with no incoming edges."""
        return tuple(task_id for task_id in self.task_ids if self.in_degree(task_id) == 0)

    def leaves(self) -> tuple[TaskId, ...]:
        """Return known tasks with no outgoing edges."""
        return tuple(task_id for task_id in self.task_ids if self.out_degree(task_id) == 0)

    def _require_known_task(self, task_id: TaskId) -> None:
        if task_id not in self._nodes_by_id:
            raise KeyError(f"Unknown graph task '{task_id}'.")


__all__ = ["DependencyGraph", "GraphEdge", "GraphNode"]
