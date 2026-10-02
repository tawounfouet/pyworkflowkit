"""LOT-02 builder and decorator conformance."""

from __future__ import annotations

from pyworkflowkit.authoring import (
    TaskDefinition,
    WorkflowDefinition,
    WorkflowDefinitionBuilder,
    WorkflowTemplate,
    task,
    workflow,
)
from pyworkflowkit.policies import TimeoutPolicy


def test_builder_creates_canonical_tasks_and_explicit_dependencies() -> None:
    builder = WorkflowDefinition.builder(name="customer_360")

    ingest_customers = builder.task(
        "ingest_customers",
        workload=lambda: "customers",
    )
    ingest_orders = builder.task(
        "ingest_orders",
        workload=lambda: "orders",
    )
    transform = builder.task(
        "transform",
        workload=lambda: "customer_360",
        depends_on=(ingest_customers, ingest_orders),
        timeout_policy=TimeoutPolicy(execution_timeout=300.0),
    )

    definition = builder.build()

    assert isinstance(builder, WorkflowDefinitionBuilder)
    assert isinstance(transform, TaskDefinition)
    assert definition.task("transform") is transform
    assert transform.dependencies == ("ingest_customers", "ingest_orders")


def test_builder_accepts_dependency_keys() -> None:
    builder = WorkflowDefinition.builder(name="demo")
    builder.task("fetch", workload=lambda: None)
    builder.task("publish", workload=lambda: None, depends_on=("fetch",))

    workflow_definition = builder.build()

    assert workflow_definition.task("publish").dependencies == ("fetch",)


def test_builder_is_mutable_but_built_definition_is_snapshot() -> None:
    builder = WorkflowDefinition.builder(name="demo")
    builder.task("first", workload=lambda: None)

    first_snapshot = builder.build()
    builder.task("second", workload=lambda: None, depends_on=("first",))
    second_snapshot = builder.build()

    assert tuple(task.key for task in first_snapshot.tasks) == ("first",)
    assert tuple(task.key for task in second_snapshot.tasks) == ("first", "second")


def test_task_decorator_returns_canonical_definition_without_execution() -> None:
    calls = 0

    @task
    def fetch() -> str:
        nonlocal calls
        calls += 1
        return "data"

    assert isinstance(fetch, TaskDefinition)
    assert fetch.key == "fetch"
    assert calls == 0


def test_task_decorator_dependencies_compile_to_keys() -> None:
    @task
    def fetch() -> str:
        return "data"

    @task(depends_on=(fetch,))
    def transform() -> str:
        return "transformed"

    assert transform.dependencies == ("fetch",)


def test_workflow_decorator_is_lazy_and_builds_canonical_definition() -> None:
    declaration_calls = 0

    @task
    def fetch() -> str:
        return "data"

    @workflow(name="demo")
    def demo() -> tuple[TaskDefinition, ...]:
        nonlocal declaration_calls
        declaration_calls += 1
        return (fetch,)

    assert isinstance(demo, WorkflowTemplate)
    assert declaration_calls == 0

    definition = demo.build()

    assert isinstance(definition, WorkflowDefinition)
    assert declaration_calls == 1
    assert definition.name == "demo"
