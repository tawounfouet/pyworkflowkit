"""LOT-03 unit tests for canonical V2 workflow planning."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pyworkflowkit.authoring import (
    RegisteredWorkload,
    TaskDefinition,
    WorkflowDefinition,
    WorkloadPortability,
)
from pyworkflowkit.planning import WorkflowPlanner


def test_compile_never_executes_workload_code() -> None:
    calls = 0

    def fetch() -> str:
        nonlocal calls
        calls += 1
        return "data"

    workflow = WorkflowDefinition(
        name="demo",
        tasks=(TaskDefinition(key="fetch", workload=fetch),),
    )

    plan = WorkflowPlanner().compile(workflow)

    assert plan.topological_order == ("fetch",)
    assert calls == 0


def test_compile_produces_deterministic_topological_order_and_groups() -> None:
    builder = WorkflowDefinition.builder(name="customer_360")
    orders = builder.task("orders", workload=RegisteredWorkload("ingest.orders"))
    customers = builder.task(
        "customers",
        workload=RegisteredWorkload("ingest.customers"),
    )
    transform = builder.task(
        "transform",
        workload=RegisteredWorkload("transform.customer_360"),
        depends_on=(orders, customers),
    )
    builder.task(
        "publish",
        workload=RegisteredWorkload("publish.customer_360"),
        depends_on=(transform,),
    )

    plan = WorkflowPlanner().compile(builder.build())

    assert plan.topological_order == (
        "customers",
        "orders",
        "transform",
        "publish",
    )
    assert plan.groups == (
        ("customers", "orders"),
        ("transform",),
        ("publish",),
    )
    assert tuple(task.position for task in plan.tasks) == (0, 1, 2, 3)
    assert tuple(task.group_index for task in plan.tasks) == (0, 0, 1, 2)


def test_semantically_equivalent_definitions_compile_to_same_plan_fingerprint() -> None:
    first = WorkflowDefinition(
        name="demo",
        tasks=(
            TaskDefinition(
                key="a",
                workload=RegisteredWorkload("jobs.a"),
            ),
            TaskDefinition(
                key="b",
                workload=RegisteredWorkload("jobs.b"),
            ),
            TaskDefinition(
                key="c",
                workload=RegisteredWorkload("jobs.c"),
                dependencies=("b", "a"),
            ),
        ),
    )
    second = WorkflowDefinition(
        name="demo",
        tasks=(
            TaskDefinition(
                key="c",
                workload=RegisteredWorkload("jobs.c"),
                dependencies=("a", "b"),
            ),
            TaskDefinition(
                key="b",
                workload=RegisteredWorkload("jobs.b"),
            ),
            TaskDefinition(
                key="a",
                workload=RegisteredWorkload("jobs.a"),
            ),
        ),
    )

    planner = WorkflowPlanner()
    first_plan = planner.compile(first)
    second_plan = planner.compile(second)

    assert first_plan.topological_order == second_plan.topological_order
    assert first_plan.groups == second_plan.groups
    assert first_plan.fingerprint() == second_plan.fingerprint()


def test_semantic_change_changes_plan_fingerprint() -> None:
    base = WorkflowDefinition(
        name="demo",
        tasks=(
            TaskDefinition(
                key="fetch",
                workload=RegisteredWorkload("jobs.fetch"),
            ),
        ),
    )
    changed = WorkflowDefinition(
        name="demo",
        tasks=(
            TaskDefinition(
                key="fetch",
                workload=RegisteredWorkload(
                    "jobs.fetch",
                    parameters=(("mode", "full"),),
                ),
            ),
        ),
    )

    planner = WorkflowPlanner()

    assert planner.compile(base).fingerprint() != planner.compile(changed).fingerprint()


def test_local_callable_requires_inline_and_emits_portability_diagnostic() -> None:
    def local() -> None:
        return None

    plan = WorkflowPlanner().compile(
        WorkflowDefinition(
            name="local",
            tasks=(TaskDefinition(key="local", workload=local),),
        )
    )

    entry = plan.task("local")
    assert entry.executor_requirement.executor_key == "inline"
    assert entry.executor_requirement.workload_kind == "python_callable"
    assert entry.portable is False
    assert plan.portable is False
    assert "executor:inline" in plan.required_capabilities
    assert "workload:python_callable" in plan.required_capabilities
    assert any(
        diagnostic.code == "PWK-PLAN-PORTABILITY-001"
        for diagnostic in plan.diagnostics
    )


def test_registered_workload_executor_requirement_is_extracted() -> None:
    plan = WorkflowPlanner().compile(
        WorkflowDefinition(
            name="registered",
            tasks=(
                TaskDefinition(
                    key="refresh",
                    workload=RegisteredWorkload(
                        "jobs.refresh",
                        executor_key="thread",
                    ),
                ),
            ),
        )
    )

    entry = plan.task("refresh")
    assert entry.executor_requirement.executor_key == "thread"
    assert entry.executor_requirement.workload_kind == "registered"
    assert entry.portable is True
    assert plan.portable is True
    assert "executor:thread" in plan.required_capabilities


@dataclass(frozen=True, slots=True)
class _PyTransformKitDescriptor:
    integration_key: str = "pytransformkit"

    @property
    def workload_kind(self) -> str:
        return "pytransformkit.transformation"

    @property
    def portability(self) -> WorkloadPortability:
        return WorkloadPortability.PORTABLE

    @property
    def executor_key(self) -> str:
        return "inline"

    def fingerprint_payload(self) -> Mapping[str, object]:
        return {
            "kind": self.workload_kind,
            "plan_ref": "customer_360",
        }


def test_integration_requirements_are_explicit_without_importing_sibling() -> None:
    plan = WorkflowPlanner().compile(
        WorkflowDefinition(
            name="cross_framework",
            tasks=(
                TaskDefinition(
                    key="transform",
                    workload=_PyTransformKitDescriptor(),
                ),
            ),
        )
    )

    assert plan.required_integrations == ("pytransformkit",)
    assert plan.task("transform").required_integrations == ("pytransformkit",)


def test_compile_emits_structured_validation_diagnostic() -> None:
    plan = WorkflowPlanner().compile(
        WorkflowDefinition(
            name="diagnostics",
            tasks=(
                TaskDefinition(
                    key="fetch",
                    workload=RegisteredWorkload("jobs.fetch"),
                ),
            ),
        )
    )

    diagnostic = plan.diagnostics[0]
    assert diagnostic.code == "PWK-PLAN-001"
    assert diagnostic.source_component == "planning"
    assert diagnostic.decision_context == "compile"
