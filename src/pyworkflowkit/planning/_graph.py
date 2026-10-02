"""Internal deterministic dependency-graph mechanics for V2 planning."""

from __future__ import annotations

from dataclasses import dataclass

from pyworkflowkit.authoring import WorkflowDefinition


@dataclass(frozen=True, slots=True)
class _DependencyEdge:
    upstream: str
    downstream: str


class _DependencyGraph:
    """Internal graph representation derived from one WorkflowDefinition."""

    __slots__ = ("_dependencies", "_downstream", "_edges", "_task_keys")

    def __init__(self, workflow: WorkflowDefinition) -> None:
        workflow.validate()

        task_keys = tuple(sorted(task.key for task in workflow.tasks))
        dependencies = {
            task.key: tuple(sorted(task.dependencies))
            for task in workflow.tasks
        }
        downstream: dict[str, list[str]] = {key: [] for key in task_keys}
        edges: list[_DependencyEdge] = []

        for task_key in task_keys:
            for dependency in dependencies[task_key]:
                downstream[dependency].append(task_key)
                edges.append(_DependencyEdge(upstream=dependency, downstream=task_key))

        self._task_keys = task_keys
        self._dependencies = dependencies
        self._downstream = {
            key: tuple(sorted(values))
            for key, values in downstream.items()
        }
        self._edges = tuple(
            sorted(edges, key=lambda edge: (edge.upstream, edge.downstream))
        )

    @property
    def task_keys(self) -> tuple[str, ...]:
        return self._task_keys

    @property
    def edges(self) -> tuple[_DependencyEdge, ...]:
        return self._edges

    def dependencies_of(self, task_key: str) -> tuple[str, ...]:
        return self._dependencies[task_key]

    def downstream_of(self, task_key: str) -> tuple[str, ...]:
        return self._downstream[task_key]

    def topological_layers(self) -> tuple[tuple[str, ...], ...]:
        """Return deterministic topological layers using lexical tie-breaking."""

        in_degree = {
            key: len(self._dependencies[key])
            for key in self._task_keys
        }
        ready = tuple(sorted(key for key, degree in in_degree.items() if degree == 0))
        layers: list[tuple[str, ...]] = []
        visited = 0

        while ready:
            layer = tuple(sorted(ready))
            layers.append(layer)
            next_ready: list[str] = []

            for task_key in layer:
                visited += 1
                for downstream in self._downstream[task_key]:
                    in_degree[downstream] -= 1
                    if in_degree[downstream] == 0:
                        next_ready.append(downstream)

            ready = tuple(sorted(next_ready))

        if visited != len(self._task_keys):
            remaining = tuple(
                sorted(key for key, degree in in_degree.items() if degree > 0)
            )
            rendered = ", ".join(remaining)
            raise ValueError(
                "workflow dependency topology contains a cycle involving: "
                f"{rendered}"
            )

        return tuple(layers)

    def topological_order(self) -> tuple[str, ...]:
        return tuple(
            task_key
            for layer in self.topological_layers()
            for task_key in layer
        )


__all__: list[str] = []
