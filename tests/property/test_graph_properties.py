"""Property tests for dependency-graph structural invariants."""

from collections.abc import Iterable

from hypothesis import given
from hypothesis import strategies as st

from pyworkflowkit.application.planning import DAGValidator, build_dependency_graph
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.ids import TaskId, WorkflowId


@st.composite
def dag_definitions(
    draw: st.DrawFn,
) -> WorkflowDefinition:
    size = draw(st.integers(min_value=1, max_value=8))
    task_ids = [TaskId(f"T{index}") for index in range(size)]

    possible_edges = [
        (upstream_index, downstream_index)
        for upstream_index in range(size)
        for downstream_index in range(upstream_index + 1, size)
    ]
    selected_edges: Iterable[tuple[int, int]] = draw(
        st.sets(st.sampled_from(possible_edges), max_size=len(possible_edges))
        if possible_edges
        else st.just(set())
    )

    dependencies_by_task: dict[TaskId, list[TaskId]] = {task_id: [] for task_id in task_ids}
    for upstream_index, downstream_index in selected_edges:
        dependencies_by_task[task_ids[downstream_index]].append(task_ids[upstream_index])

    tasks = tuple(
        TaskDefinition(
            task_id=task_id,
            depends_on=tuple(sorted(dependencies_by_task[task_id], key=str)),
        )
        for task_id in task_ids
    )
    return WorkflowDefinition(
        workflow_id=WorkflowId("property-dag"),
        version="1",
        tasks=tasks,
    )


@given(dag_definitions())
def test_generated_forward_edge_graphs_are_valid_dags(
    definition: WorkflowDefinition,
) -> None:
    graph = build_dependency_graph(definition)

    DAGValidator().validate(definition, graph)

    assert set(graph.task_ids) == {task.task_id for task in definition.tasks}


@given(dag_definitions())
def test_graph_adjacency_is_consistent_for_generated_dags(
    definition: WorkflowDefinition,
) -> None:
    graph = build_dependency_graph(definition)

    for edge in graph.edges:
        assert edge.upstream_task_id in graph.upstream_of(edge.downstream_task_id)
        assert edge.downstream_task_id in graph.downstream_of(edge.upstream_task_id)
