"""Dependency-graph construction, validation, planning, and readiness services."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from heapq import heapify, heappop, heappush

from pyworkflowkit.domain.definitions import WorkflowDefinition
from pyworkflowkit.domain.enums import TaskRunStatus
from pyworkflowkit.domain.graph import DependencyGraph, GraphEdge, GraphNode
from pyworkflowkit.domain.ids import TaskId, WorkflowId, validate_non_empty_identifier
from pyworkflowkit.domain.runtime import TaskRun
from pyworkflowkit.errors import (
    CycleDetectedError,
    DuplicateDependencyError,
    InvalidExecutionPlanError,
    PlanningInvariantError,
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


@dataclass(frozen=True, slots=True)
class PlannedTask:
    """One task positioned inside a deterministic execution plan."""

    task_id: TaskId
    position: int
    group_index: int

    def __post_init__(self) -> None:
        validate_non_empty_identifier(str(self.task_id), field_name="task_id")
        _validate_non_negative_integer(self.position, field_name="position")
        _validate_non_negative_integer(self.group_index, field_name="group_index")


@dataclass(frozen=True, slots=True)
class ExecutionGroup:
    """Tasks that are structurally eligible at the same topological layer."""

    index: int
    task_ids: tuple[TaskId, ...]

    def __post_init__(self) -> None:
        _validate_non_negative_integer(self.index, field_name="index")
        task_ids = tuple(self.task_ids)
        if not task_ids:
            raise InvalidExecutionPlanError(reason="execution group must not be empty")
        if len(task_ids) != len(set(task_ids)):
            raise InvalidExecutionPlanError(
                reason=f"execution group {self.index} contains duplicate tasks"
            )
        for task_id in task_ids:
            validate_non_empty_identifier(str(task_id), field_name="task_id")
        object.__setattr__(self, "task_ids", task_ids)


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Deterministic static plan derived from a validated workflow DAG."""

    workflow_id: WorkflowId
    workflow_version: str
    tasks: tuple[PlannedTask, ...]
    groups: tuple[ExecutionGroup, ...]

    def __post_init__(self) -> None:
        validate_non_empty_identifier(str(self.workflow_id), field_name="workflow_id")
        validate_non_empty_identifier(
            self.workflow_version,
            field_name="workflow_version",
        )

        tasks = tuple(self.tasks)
        groups = tuple(self.groups)
        if not tasks:
            raise InvalidExecutionPlanError(reason="execution plan must contain tasks")
        if not groups:
            raise InvalidExecutionPlanError(reason="execution plan must contain groups")

        positions = tuple(task.position for task in tasks)
        if positions != tuple(range(len(tasks))):
            raise InvalidExecutionPlanError(
                reason="planned task positions must be contiguous from zero"
            )

        group_indices = tuple(group.index for group in groups)
        if group_indices != tuple(range(len(groups))):
            raise InvalidExecutionPlanError(
                reason="execution group indices must be contiguous from zero"
            )

        planned_task_ids = tuple(task.task_id for task in tasks)
        if len(planned_task_ids) != len(set(planned_task_ids)):
            raise InvalidExecutionPlanError(
                reason="each task must appear exactly once in the execution plan"
            )

        flattened_group_task_ids = tuple(task_id for group in groups for task_id in group.task_ids)
        if flattened_group_task_ids != planned_task_ids:
            raise InvalidExecutionPlanError(
                reason="execution groups must match planned task ordering exactly"
            )

        group_by_task_id = {task_id: group.index for group in groups for task_id in group.task_ids}
        for task in tasks:
            if group_by_task_id[task.task_id] != task.group_index:
                raise InvalidExecutionPlanError(
                    reason=(
                        f"planned task '{task.task_id}' has inconsistent group index "
                        f"{task.group_index}"
                    )
                )

        object.__setattr__(self, "tasks", tasks)
        object.__setattr__(self, "groups", groups)

    @property
    def task_ids(self) -> tuple[TaskId, ...]:
        """Return planned task identifiers in deterministic plan order."""
        return tuple(task.task_id for task in self.tasks)

    def group_for(self, task_id: TaskId) -> ExecutionGroup:
        """Return the execution group containing a planned task."""
        for group in self.groups:
            if task_id in group.task_ids:
                return group
        raise KeyError(f"Task '{task_id}' is not present in the execution plan.")


class ExecutionPlanner:
    """Build deterministic topological plans from already validated DAGs."""

    def build_plan(
        self,
        workflow: WorkflowDefinition,
        graph: DependencyGraph,
    ) -> ExecutionPlan:
        workflow_task_ids = tuple(sorted((task.task_id for task in workflow.tasks), key=str))
        if graph.task_ids != workflow_task_ids:
            raise PlanningInvariantError(
                reason="workflow definition and dependency graph contain different tasks"
            )

        in_degree = {task_id: graph.in_degree(task_id) for task_id in graph.task_ids}
        ready = tuple(task_id for task_id in graph.task_ids if in_degree[task_id] == 0)

        groups: list[ExecutionGroup] = []
        planned_tasks: list[PlannedTask] = []
        position = 0
        group_index = 0

        while ready:
            group_task_ids = tuple(sorted(ready, key=str))
            groups.append(ExecutionGroup(index=group_index, task_ids=group_task_ids))

            next_ready: list[TaskId] = []
            for task_id in group_task_ids:
                planned_tasks.append(
                    PlannedTask(
                        task_id=task_id,
                        position=position,
                        group_index=group_index,
                    )
                )
                position += 1

                for downstream_task_id in graph.downstream_of(task_id):
                    in_degree[downstream_task_id] -= 1
                    if in_degree[downstream_task_id] == 0:
                        next_ready.append(downstream_task_id)

            ready = tuple(sorted(next_ready, key=str))
            group_index += 1

        if len(planned_tasks) != len(graph.task_ids):
            remaining = tuple(
                sorted(
                    (task_id for task_id in graph.task_ids if in_degree[task_id] > 0),
                    key=str,
                )
            )
            rendered = ", ".join(str(task_id) for task_id in remaining)
            raise PlanningInvariantError(
                reason=f"graph could not be fully planned; remaining tasks: {rendered}"
            )

        return ExecutionPlan(
            workflow_id=workflow.workflow_id,
            workflow_version=workflow.version,
            tasks=tuple(planned_tasks),
            groups=tuple(groups),
        )


class ReadyTaskResolver:
    """Resolve runtime eligibility independently from static plan construction."""

    def is_ready(
        self,
        *,
        task_run: TaskRun,
        graph: DependencyGraph,
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
    ) -> bool:
        self._ensure_task_run_matches_graph(task_run=task_run, graph=graph)

        if task_run.status is not TaskRunStatus.PENDING:
            return False

        for upstream_task_id in graph.upstream_of(task_run.task_id):
            upstream_run = task_runs_by_task_id.get(upstream_task_id)
            if upstream_run is None:
                raise PlanningInvariantError(
                    reason=f"missing TaskRun for upstream task '{upstream_task_id}'"
                )
            self._ensure_mapping_identity(upstream_task_id, upstream_run)
            if upstream_run.status is not TaskRunStatus.SUCCEEDED:
                return False

        return True

    def find_ready(
        self,
        *,
        graph: DependencyGraph,
        task_runs_by_task_id: Mapping[TaskId, TaskRun],
    ) -> tuple[TaskRun, ...]:
        ready: list[TaskRun] = []
        for task_id in graph.task_ids:
            task_run = task_runs_by_task_id.get(task_id)
            if task_run is None:
                raise PlanningInvariantError(reason=f"missing TaskRun for graph task '{task_id}'")
            self._ensure_mapping_identity(task_id, task_run)
            if self.is_ready(
                task_run=task_run,
                graph=graph,
                task_runs_by_task_id=task_runs_by_task_id,
            ):
                ready.append(task_run)
        return tuple(ready)

    @staticmethod
    def _ensure_task_run_matches_graph(
        *,
        task_run: TaskRun,
        graph: DependencyGraph,
    ) -> None:
        if task_run.task_id not in graph.task_ids:
            raise PlanningInvariantError(
                reason=f"TaskRun references task '{task_run.task_id}' absent from graph"
            )

    @staticmethod
    def _ensure_mapping_identity(task_id: TaskId, task_run: TaskRun) -> None:
        if task_run.task_id != task_id:
            raise PlanningInvariantError(
                reason=(
                    f"TaskRun mapping key '{task_id}' does not match "
                    f"TaskRun task_id '{task_run.task_id}'"
                )
            )


def _validate_non_negative_integer(value: int, *, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} must be greater than or equal to 0.")


__all__ = [
    "DAGValidator",
    "ExecutionGroup",
    "ExecutionPlan",
    "ExecutionPlanner",
    "PlannedTask",
    "ReadyTaskResolver",
    "build_dependency_graph",
]
