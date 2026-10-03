"""Unit tests for LOT-32 declarative flow operators (>> and <<)."""

from __future__ import annotations

import pytest

from pyworkflowkit.authoring import (
    TaskDefinition,
    WorkflowDefinition,
    task,
    workflow,
)
from pyworkflowkit.authoring.builders import WorkflowDefinitionBuilder
from pyworkflowkit.authoring.definitions import TaskSequence
from pyworkflowkit.authoring.validation import CircularDependencyError
from pyworkflowkit.domain.ids import TaskId


def _workload_a() -> str:
    return "a"


def _workload_b() -> str:
    return "b"


def _workload_c() -> str:
    return "c"


def _workload_d() -> str:
    return "d"


def test_linear_task_rshift_chain() -> None:
    t1 = TaskDefinition(key="t1", workload=_workload_a)
    t2 = TaskDefinition(key="t2", workload=_workload_b)
    t3 = TaskDefinition(key="t3", workload=_workload_c)

    # Chain t1 >> t2 >> t3
    res = t1 >> t2 >> t3
    assert res is t3
    assert t1.dependencies == ()
    assert t2.dependencies == ("t1",)
    assert t3.dependencies == ("t2",)


def test_fan_out_operator() -> None:
    t1 = TaskDefinition(key="t1", workload=_workload_a)
    t2 = TaskDefinition(key="t2", workload=_workload_b)
    t3 = TaskDefinition(key="t3", workload=_workload_c)

    # t1 >> [t2, t3]
    res = t1 >> [t2, t3]
    assert isinstance(res, TaskSequence)
    assert len(res) == 2
    assert t2.dependencies == ("t1",)
    assert t3.dependencies == ("t1",)


def test_fan_in_operator() -> None:
    t1 = TaskDefinition(key="t1", workload=_workload_a)
    t2 = TaskDefinition(key="t2", workload=_workload_b)
    t3 = TaskDefinition(key="t3", workload=_workload_c)

    # [t1, t2] >> t3
    res = [t1, t2] >> t3
    assert res is t3
    assert t3.dependencies == ("t1", "t2")


def test_fan_out_then_fan_in_combination() -> None:
    t1 = TaskDefinition(key="t1", workload=_workload_a)
    t2 = TaskDefinition(key="t2", workload=_workload_b)
    t3 = TaskDefinition(key="t3", workload=_workload_c)
    t4 = TaskDefinition(key="t4", workload=_workload_d)

    # t1 >> [t2, t3] >> t4
    res = t1 >> [t2, t3] >> t4
    assert res is t4
    assert t2.dependencies == ("t1",)
    assert t3.dependencies == ("t1",)
    assert t4.dependencies == ("t2", "t3")


def test_lshift_operators() -> None:
    t1 = TaskDefinition(key="t1", workload=_workload_a)
    t2 = TaskDefinition(key="t2", workload=_workload_b)
    t3 = TaskDefinition(key="t3", workload=_workload_c)

    # t2 << t1 (t2 depends on t1)
    res = t2 << t1
    assert res is t2
    assert t2.dependencies == ("t1",)

    # t3 << [t1, t2]
    res_fan_in = t3 << [t1, t2]
    assert res_fan_in is t3
    assert t3.dependencies == ("t1", "t2")


def test_task_sequence_helpers() -> None:
    t1 = TaskDefinition(key="t1", workload=_workload_a)
    t2 = TaskDefinition(key="t2", workload=_workload_b)
    seq = TaskSequence([t1, t2])

    assert len(seq) == 2
    assert seq[0] is t1
    assert seq[1] is t2
    assert [t.key for t in seq] == ["t1", "t2"]
    assert "t1" in repr(seq)
    assert isinstance(seq[:1], TaskSequence)


def test_subworkflow_composition_as_task() -> None:
    sub_t1 = TaskDefinition(key="sub_step1", workload=_workload_a)
    sub_t2 = TaskDefinition(key="sub_step2", workload=_workload_b)
    sub_t1 >> sub_t2
    subflow = WorkflowDefinition(name="nested_pipeline", tasks=(sub_t1, sub_t2))

    assert subflow.workload_kind == "workflow"
    assert subflow.fingerprint_payload()["kind"] == "workflow"

    # Use as_task helper
    parent_init = TaskDefinition(key="init", workload=_workload_c)
    composite_task = subflow.as_task(key="run_nested")
    parent_final = TaskDefinition(key="final", workload=_workload_d)

    parent_init >> composite_task >> parent_final

    parent_flow = WorkflowDefinition(
        name="parent_pipeline",
        tasks=(parent_init, composite_task, parent_final),
    )
    parent_flow.validate()

    assert composite_task.workload is subflow
    assert composite_task.dependencies == ("init",)
    assert parent_final.dependencies == ("run_nested",)


def test_decorator_workflow_flow_chaining() -> None:
    @task
    def step_a() -> str:
        return "a"

    @task
    def step_b() -> str:
        return "b"

    @task
    def step_c() -> str:
        return "c"

    @workflow(name="decorated_chain")
    def my_pipeline() -> list[TaskDefinition]:
        a = step_a
        b = step_b
        c = step_c
        a >> b >> c
        return [a, b, c]

    flow = my_pipeline.build()
    flow.validate()

    assert flow.task("step_b").dependencies == ("step_a",)
    assert flow.task("step_c").dependencies == ("step_b",)


def test_reverse_lshift_and_sequence_operators() -> None:
    t1 = TaskDefinition(key="t1", workload=_workload_a)
    t2 = TaskDefinition(key="t2", workload=_workload_b)
    t3 = TaskDefinition(key="t3", workload=_workload_c)

    # [t2, t3] << t1 (triggers __rlshift__)
    res_rlshift = [t2, t3] << t1
    assert isinstance(res_rlshift, TaskSequence)
    assert t2.dependencies == ("t1",)
    assert t3.dependencies == ("t1",)

    # TaskSequence >> Sequence
    t4 = TaskDefinition(key="t4", workload=_workload_d)
    t5 = TaskDefinition(key="t5", workload=_workload_a)
    seq = TaskSequence([t2, t3])
    res_seq_seq = seq >> [t4, t5]
    assert isinstance(res_seq_seq, TaskSequence)
    assert t4.dependencies == ("t2", "t3")
    assert t5.dependencies == ("t2", "t3")

    # TaskSequence << TaskDefinition
    t0 = TaskDefinition(key="t0", workload=_workload_a)
    res_seq_left = seq << t0
    assert res_seq_left is seq
    assert set(t2.dependencies) == {"t1", "t0"}
    assert set(t3.dependencies) == {"t1", "t0"}

    # TaskSequence << Sequence
    t_pre1 = TaskDefinition(key="pre1", workload=_workload_a)
    t_pre2 = TaskDefinition(key="pre2", workload=_workload_b)
    res_seq_left_seq = seq << [t_pre1, t_pre2]
    assert res_seq_left_seq is seq
    assert "pre1" in t2.dependencies
    assert "pre2" in t2.dependencies


def test_invalid_flow_operator_types() -> None:
    t_src = TaskDefinition(key="t_src", workload=_workload_a)
    t_dst = TaskDefinition(key="t_dst", workload=_workload_b)
    seq = TaskSequence([t_src, t_dst])

    with pytest.raises(TypeError):
        _ = t_src >> 123  # type: ignore[operator]

    with pytest.raises(TypeError):
        _ = 123 >> t_src  # type: ignore[operator]

    with pytest.raises(TypeError):
        _ = t_src << 123  # type: ignore[operator]

    with pytest.raises(TypeError):
        _ = 123 << t_src  # type: ignore[operator]

    with pytest.raises(TypeError):
        _ = t_src >> [t_dst, "bad"]  # type: ignore[list-item]

    with pytest.raises(TypeError):
        _ = [t_src, "bad"] >> t_dst  # type: ignore[operator]

    with pytest.raises(TypeError):
        _ = t_src << [t_dst, "bad"]  # type: ignore[list-item]

    with pytest.raises(TypeError):
        _ = [t_src, "bad"] << t_dst  # type: ignore[operator]

    with pytest.raises(TypeError):
        _ = seq >> 123  # type: ignore[operator]

    with pytest.raises(TypeError):
        _ = seq << 123  # type: ignore[operator]

    with pytest.raises(TypeError):
        _ = seq >> [t_dst, "bad"]  # type: ignore[list-item]

    with pytest.raises(TypeError):
        _ = seq << [t_src, "bad"]  # type: ignore[list-item]


def test_builder_context_manager_and_add_task() -> None:
    with WorkflowDefinitionBuilder(name="cm_flow") as wb:
        _t1 = wb.task(key="t1", workload=_workload_a)
        t2 = TaskDefinition(key="t2", workload=_workload_b)
        wb.add_task(t2)

        # Duplicate in task()
        with pytest.raises(ValueError, match="already contains"):
            wb.task(key="t1", workload=_workload_a)

        # Non-TaskDefinition in add()
        with pytest.raises(TypeError, match="must be a TaskDefinition"):
            wb.add("not_a_task")  # type: ignore[arg-type]

        # Duplicate in add()
        with pytest.raises(ValueError, match="already contains"):
            wb.add(t2)

    flow = wb.build()
    assert len(flow.tasks) == 2

    # CircularDependencyError constructors
    err_empty = CircularDependencyError()
    assert err_empty.cycle_path == ()

    err_ids = CircularDependencyError(task_ids=[TaskId("a"), TaskId("b")])
    assert err_ids.cycle_path == ("a", "b")
