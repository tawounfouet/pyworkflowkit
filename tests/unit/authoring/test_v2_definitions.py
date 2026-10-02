"""LOT-02 unit tests for canonical immutable workflow authoring."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from pyworkflowkit.authoring import (
    InputDeclaration,
    OutputDeclaration,
    RegisteredWorkload,
    TaskDefinition,
    WorkflowDefinition,
)
from pyworkflowkit.policies import TimeoutPolicy, TriggerRule


def _noop() -> None:
    return None


def test_task_definition_is_one_workload_boundary_and_does_not_execute() -> None:
    calls = 0

    def workload() -> str:
        nonlocal calls
        calls += 1
        return "done"

    task = TaskDefinition(key="fetch", workload=workload)

    assert task.key == "fetch"
    assert task.workload is workload
    assert calls == 0
    assert task.dependencies == ()
    assert task.trigger_rule is TriggerRule.ALL_SUCCESS


def test_task_definition_contains_no_runtime_execution_state() -> None:
    task = TaskDefinition(key="fetch", workload=_noop)

    forbidden = {
        "workflow_run_id",
        "task_run_id",
        "task_attempt_id",
        "attempt_number",
        "external_run_id",
        "status",
    }
    assert forbidden.isdisjoint(task.__dataclass_fields__)


def test_task_definition_normalizes_dependency_and_io_sequences() -> None:
    task = TaskDefinition(
        key="transform",
        workload=_noop,
        dependencies=("ingest_customers", "ingest_orders"),
        timeout_policy=TimeoutPolicy(execution_timeout=30.0),
        trigger_rule=TriggerRule.ALL_SUCCESS,
        inputs=(InputDeclaration("customers"), InputDeclaration("orders")),
        outputs=(OutputDeclaration("customer_360"),),
        metadata={"team": "data", "labels": ["daily", "customer"]},
    )

    assert task.dependencies == ("ingest_customers", "ingest_orders")
    assert tuple(item.name for item in task.inputs) == ("customers", "orders")
    assert tuple(item.name for item in task.outputs) == ("customer_360",)
    assert task.metadata["labels"] == ("daily", "customer")


def test_task_definition_rejects_duplicate_or_self_dependencies() -> None:
    with pytest.raises(ValueError, match="duplicate dependencies"):
        TaskDefinition(
            key="transform",
            workload=_noop,
            dependencies=("ingest", "ingest"),
        )

    with pytest.raises(ValueError, match="cannot depend on itself"):
        TaskDefinition(
            key="transform",
            workload=_noop,
            dependencies=("transform",),
        )


def test_task_definition_rejects_duplicate_io_names() -> None:
    with pytest.raises(ValueError, match="duplicate input"):
        TaskDefinition(
            key="transform",
            workload=_noop,
            inputs=(InputDeclaration("source"), InputDeclaration("source")),
        )

    with pytest.raises(ValueError, match="duplicate output"):
        TaskDefinition(
            key="transform",
            workload=_noop,
            outputs=(OutputDeclaration("result"), OutputDeclaration("result")),
        )


def test_local_callable_is_explicitly_non_portable() -> None:
    task = TaskDefinition(key="local", workload=_noop)

    assert task.portable is False


def test_registered_workload_is_portable_and_canonicalizes_parameters() -> None:
    workload = RegisteredWorkload(
        registry_key="jobs.refresh_cache",
        parameters=(("region", "eu"), ("mode", "full")),
        executor_key="inline",
    )
    task = TaskDefinition(key="refresh", workload=workload)

    assert task.portable is True
    assert workload.parameters == (("mode", "full"), ("region", "eu"))


def test_workflow_rejects_duplicate_unknown_and_cyclic_topology() -> None:
    a = TaskDefinition(key="a", workload=_noop)
    duplicate_a = TaskDefinition(key="a", workload=_noop)

    with pytest.raises(ValueError, match="duplicate task key"):
        WorkflowDefinition(name="duplicate", tasks=(a, duplicate_a))

    unknown = TaskDefinition(key="b", workload=_noop, dependencies=("missing",))
    with pytest.raises(ValueError, match="unknown task"):
        WorkflowDefinition(name="unknown", tasks=(a, unknown))

    cycle_a = TaskDefinition(key="a", workload=_noop, dependencies=("b",))
    cycle_b = TaskDefinition(key="b", workload=_noop, dependencies=("a",))
    with pytest.raises(ValueError, match="contains a cycle"):
        WorkflowDefinition(name="cycle", tasks=(cycle_a, cycle_b))


def test_workflow_definition_is_immutable() -> None:
    workflow = WorkflowDefinition(
        name="demo",
        tasks=(TaskDefinition(key="fetch", workload=_noop),),
    )

    with pytest.raises(FrozenInstanceError):
        workflow.name = "other"  # type: ignore[misc]


def test_metadata_is_deeply_frozen() -> None:
    workflow = WorkflowDefinition(
        name="demo",
        tasks=(TaskDefinition(key="fetch", workload=_noop),),
        metadata={"labels": ["daily"], "nested": {"owner": "data"}},
    )

    labels = workflow.metadata["labels"]
    nested = workflow.metadata["nested"]

    assert labels == ("daily",)
    with pytest.raises(TypeError):
        nested["owner"] = "other"  # type: ignore[index]


def test_workflow_explain_is_deterministic_and_inspection_only() -> None:
    calls = 0

    def workload() -> None:
        nonlocal calls
        calls += 1

    workflow = WorkflowDefinition(
        name="demo",
        tasks=(TaskDefinition(key="fetch", workload=workload),),
    )

    first = workflow.explain()
    second = workflow.explain()

    assert first == second
    assert "WorkflowDefinition" in first
    assert "fetch" in first
    assert calls == 0
