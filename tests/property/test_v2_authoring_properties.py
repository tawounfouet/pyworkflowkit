"""Hypothesis property tests for V2 authoring flow operators and cycle detection."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.authoring.validation import CircularDependencyError


def _noop() -> None:
    pass


@st.composite
def random_dag_edges(
    draw: st.DrawFn,
) -> tuple[int, list[tuple[int, int]]]:
    """Generate a random valid DAG topology with nodes indexed 0..N-1."""
    num_nodes = draw(st.integers(min_value=2, max_value=20))
    possible_edges = [(i, j) for i in range(num_nodes) for j in range(i + 1, num_nodes)]
    edges = draw(
        st.lists(
            st.sampled_from(possible_edges),
            unique=True,
            max_size=min(len(possible_edges), 35),
        )
        if possible_edges
        else st.just([])
    )
    return num_nodes, edges


@settings(max_examples=100)
@given(random_dag_edges())
def test_authoring_valid_dag_never_raises_cycle_error(
    scenario: tuple[int, list[tuple[int, int]]],
) -> None:
    num_nodes, edges = scenario
    tasks = [TaskDefinition(key=f"task_{i}", workload=_noop) for i in range(num_nodes)]

    # Adding valid forward edges (i < j) should never raise CircularDependencyError
    for u, v in edges:
        _ = tasks[u] >> tasks[v]

    workflow = WorkflowDefinition(
        name="hypothesis_dag",
        tasks=tuple(tasks),
    )
    workflow.validate()
    assert len(workflow.tasks) == num_nodes


@settings(max_examples=50)
@given(st.integers(min_value=2, max_value=15))
def test_authoring_chain_backward_edge_always_raises_circular_dependency_error(
    chain_length: int,
) -> None:
    tasks = [TaskDefinition(key=f"chain_{i}", workload=_noop) for i in range(chain_length)]

    # Chain sequentially: tasks[0] >> tasks[1] >> ... >> tasks[N-1]
    for i in range(chain_length - 1):
        _ = tasks[i] >> tasks[i + 1]

    # Any backward edge from tasks[j] to tasks[i] where j >= i must raise immediately
    last_task = tasks[-1]
    first_task = tasks[0]

    with pytest.raises(CircularDependencyError) as exc_info:
        _ = last_task >> first_task

    assert "Cycle detected" in str(exc_info.value)
    assert exc_info.value.cycle_path[0] == first_task.key
    assert exc_info.value.cycle_path[-1] == first_task.key
