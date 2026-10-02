"""LOT-02 deterministic WorkflowDefinition fingerprint tests."""

from __future__ import annotations

from pyworkflowkit.authoring import RegisteredWorkload, TaskDefinition, WorkflowDefinition


def _registered(name: str) -> RegisteredWorkload:
    return RegisteredWorkload(registry_key=name)


def test_semantically_identical_definitions_have_same_fingerprint() -> None:
    first = WorkflowDefinition(
        name="customer_360",
        tasks=(
            TaskDefinition(key="customers", workload=_registered("ingest.customers")),
            TaskDefinition(key="orders", workload=_registered("ingest.orders")),
            TaskDefinition(
                key="transform",
                workload=_registered("transform.customer_360"),
                dependencies=("customers", "orders"),
            ),
        ),
        metadata={"owner": "data", "labels": ["daily", "customer"]},
    )

    second = WorkflowDefinition(
        name="customer_360",
        tasks=(
            TaskDefinition(
                key="transform",
                workload=_registered("transform.customer_360"),
                dependencies=("orders", "customers"),
            ),
            TaskDefinition(key="orders", workload=_registered("ingest.orders")),
            TaskDefinition(key="customers", workload=_registered("ingest.customers")),
        ),
        metadata={"labels": ["daily", "customer"], "owner": "data"},
    )

    assert first.fingerprint() == second.fingerprint()
    assert first.fingerprint().startswith("sha256:")


def test_semantic_change_changes_fingerprint() -> None:
    base = WorkflowDefinition(
        name="demo",
        tasks=(TaskDefinition(key="fetch", workload=_registered("jobs.fetch")),),
    )
    changed = WorkflowDefinition(
        name="demo",
        tasks=(
            TaskDefinition(
                key="fetch",
                workload=RegisteredWorkload(
                    registry_key="jobs.fetch",
                    parameters=(("mode", "full"),),
                ),
            ),
        ),
    )

    assert base.fingerprint() != changed.fingerprint()


def test_fingerprint_does_not_execute_local_callable() -> None:
    calls = 0

    def local() -> None:
        nonlocal calls
        calls += 1

    definition = WorkflowDefinition(
        name="local",
        tasks=(TaskDefinition(key="local", workload=local),),
    )

    assert definition.fingerprint().startswith("sha256:")
    assert calls == 0
