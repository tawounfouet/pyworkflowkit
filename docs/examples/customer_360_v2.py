"""Customer 360 v2 canonical pipeline demonstration for PyWorkflowKit 2.1.

Demonstrates:
- Fluid authoring operators (>> and <<) introduced in LOT-32
- Typed dependency output extraction via TaskExecutionContext
- Resilient runtime execution with SQLite metadata persistence
- Full workflow lifecycle and run inspection
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pyworkflowkit.authoring import WorkflowDefinition, task
from pyworkflowkit.executors import InlineExecutor, TaskExecutionContext
from pyworkflowkit.persistence import SQLiteMetadataStore
from pyworkflowkit.runtime import WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus


@task(key="ingest_customers")
def ingest_customers() -> dict[str, int]:
    """Ingest customers dataset."""
    return {"customers_count": 1000}


@task(key="ingest_orders")
def ingest_orders() -> dict[str, int]:
    """Ingest orders dataset."""
    return {"orders_count": 5000}


@task(key="reconcile_360")
def reconcile_360(context: TaskExecutionContext) -> dict[str, object]:
    """Reconcile customer profiles with orders."""
    customers = context.dependency_outputs["ingest_customers"]["customers_count"]
    orders = context.dependency_outputs["ingest_orders"]["orders_count"]
    return {
        "reconciled": True,
        "total_customers": customers,
        "total_orders": orders,
        "ratio": orders / customers if customers else 0.0,
    }


# Declare dependency graph using LOT-32 fluid flow operator (fan-in)
[ingest_customers, ingest_orders] >> reconcile_360

# Compose into canonical WorkflowDefinition
customer_360_workflow = WorkflowDefinition(
    name="customer_360_v2",
    tasks=(ingest_customers, ingest_orders, reconcile_360),
)


def main() -> int:
    """Execute customer 360 pipeline in an isolated SQLite database."""
    with tempfile.TemporaryDirectory(prefix="pwk-customer360-") as temp_dir:
        db_path = Path(temp_dir) / "customer_360.db"
        store = SQLiteMetadataStore(f"sqlite:///{db_path}")
        runtime = WorkflowRuntime(metadata=store, executor=InlineExecutor())

        print("Executing Customer 360 v2 workflow...")
        result = runtime.run(customer_360_workflow)
        print(f"Workflow status: {result.status.value}")
        print(f"Workflow run ID: {result.run_id}")
        print(f"Reconciliation output: {result.task('reconcile_360').output}")

        assert result.status is WorkflowRunStatus.SUCCEEDED
        assert result.task("reconcile_360").output["reconciled"] is True
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
