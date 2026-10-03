"""Unit tests for LOT-32 instant cycle detection and CircularDependencyError."""

from __future__ import annotations

import pytest

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinitionBuilder
from pyworkflowkit.authoring.validation import CircularDependencyError


def _noop() -> None:
    pass


def test_self_dependency_raises_circular_dependency_error_immediately() -> None:
    t = TaskDefinition(key="self_node", workload=_noop)
    with pytest.raises(CircularDependencyError) as exc_info:
        _ = t >> t
    assert "Cycle detected" in str(exc_info.value)
    assert "self_node" in exc_info.value.cycle_path


def test_two_node_cycle_raises_immediately() -> None:
    a = TaskDefinition(key="node_a", workload=_noop)
    b = TaskDefinition(key="node_b", workload=_noop)

    a >> b
    assert b.dependencies == ("node_a",)

    # Attempting b >> a creates a -> b -> a
    with pytest.raises(CircularDependencyError) as exc_info:
        _ = b >> a

    assert "Cycle detected" in str(exc_info.value)
    assert exc_info.value.cycle_path == ("node_a", "node_b", "node_a")


def test_three_node_transitive_cycle_raises_immediately() -> None:
    a = TaskDefinition(key="step_1", workload=_noop)
    b = TaskDefinition(key="step_2", workload=_noop)
    c = TaskDefinition(key="step_3", workload=_noop)

    a >> b >> c
    assert b.dependencies == ("step_1",)
    assert c.dependencies == ("step_2",)

    # Attempting c >> a closes the loop
    with pytest.raises(CircularDependencyError) as exc_info:
        _ = c >> a

    assert "Cycle detected" in str(exc_info.value)
    assert exc_info.value.cycle_path == ("step_1", "step_2", "step_3", "step_1")


def test_fan_out_cycle_raises_immediately() -> None:
    a = TaskDefinition(key="root", workload=_noop)
    b = TaskDefinition(key="branch_1", workload=_noop)
    c = TaskDefinition(key="branch_2", workload=_noop)

    a >> [b, c]

    # Attempting c >> a
    with pytest.raises(CircularDependencyError) as exc_info:
        _ = c >> a

    assert "Cycle detected" in str(exc_info.value)
    assert exc_info.value.cycle_path == ("root", "branch_2", "root")


def test_builder_detects_cycle_immediately_on_add_task() -> None:
    builder = WorkflowDefinitionBuilder(name="cyclic_flow")
    t1 = TaskDefinition(key="alpha", workload=_noop)
    t2 = TaskDefinition(key="beta", workload=_noop, dependencies=("alpha",))
    t3 = TaskDefinition(key="gamma", workload=_noop, dependencies=("beta",))

    builder.add(t1)
    builder.add(t2)
    builder.add(t3)

    # Attempting to add a cyclic task definition directly
    cyclic_task = TaskDefinition(key="delta", workload=_noop, dependencies=("gamma",))
    builder.add(cyclic_task)

    # Introducing a task that loops back: alpha depending on delta
    # If someone tries to re-add or mutate
    t_loop = TaskDefinition(key="epsilon", workload=_noop, dependencies=("delta",))
    builder.add(t_loop)


def test_builder_task_method_detects_cycle_immediately() -> None:
    builder = WorkflowDefinitionBuilder(name="builder_cyclic")
    t_a = TaskDefinition(key="a", workload=_noop, dependencies=("c",))
    t_b = TaskDefinition(key="b", workload=_noop, dependencies=("a",))
    t_c = TaskDefinition(key="c", workload=_noop, dependencies=("b",))

    builder.add(t_a)
    builder.add(t_b)
    with pytest.raises(CircularDependencyError) as exc_info:
        builder.add(t_c)

    assert "Cycle detected" in str(exc_info.value)


def test_complex_dag_cycle_rejection() -> None:
    t1 = TaskDefinition(key="t1", workload=_noop)
    t2 = TaskDefinition(key="t2", workload=_noop)
    t3 = TaskDefinition(key="t3", workload=_noop)
    t4 = TaskDefinition(key="t4", workload=_noop)
    t5 = TaskDefinition(key="t5", workload=_noop)

    t1 >> t2 >> t4
    t1 >> t3 >> t4
    t4 >> t5

    # Any backward edge from t5 to t1, t2, t3, or t4 must raise immediately
    with pytest.raises(CircularDependencyError):
        _ = t5 >> t1

    with pytest.raises(CircularDependencyError):
        _ = t5 >> t2

    with pytest.raises(CircularDependencyError):
        _ = t5 >> t3

    with pytest.raises(CircularDependencyError):
        _ = t5 >> t4
