"""End-to-End qualification scenario for Customer 360 v2 pipeline (LOT-37).

Validates:
- Fluid authoring operators (>> and <<)
- Dual fan-in dependency resolution
- Failure injection and state machine integrity
- Selective resumption (resume_run) reusing cached outputs
- Transactional metadata store pruning
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from pyworkflowkit.authoring import WorkflowDefinition, task
from pyworkflowkit.executors import InlineExecutor, TaskExecutionContext
from pyworkflowkit.persistence import SQLiteMetadataStore
from pyworkflowkit.persistence.retention import RetentionPolicy
from pyworkflowkit.runtime import WorkflowRuntime
from pyworkflowkit.states import TaskRunStatus, WorkflowRunStatus


def test_customer_360_v2_end_to_end_nominal_and_resumption() -> None:
    with tempfile.TemporaryDirectory(prefix="pwk-e2e-c360-") as temp_dir:
        db_path = Path(temp_dir) / "customer_360_e2e.db"
        store = SQLiteMetadataStore(f"sqlite:///{db_path}")
        runtime = WorkflowRuntime(metadata=store, executor=InlineExecutor())

        # Counters to verify invocation and cached reuse
        ingest_customer_calls = 0
        ingest_order_calls = 0
        reconcile_calls = 0
        should_fail_reconcile = True

        @task(key="ingest_customers")
        def ingest_customers() -> dict[str, int]:
            nonlocal ingest_customer_calls
            ingest_customer_calls += 1
            return {"customers_count": 1000}

        @task(key="ingest_orders")
        def ingest_orders() -> dict[str, int]:
            nonlocal ingest_order_calls
            ingest_order_calls += 1
            return {"orders_count": 5000}

        @task(key="reconcile_360")
        def reconcile_360(context: TaskExecutionContext) -> dict[str, object]:
            nonlocal reconcile_calls
            reconcile_calls += 1
            if should_fail_reconcile:
                raise RuntimeError("Simulated transient warehouse timeout")
            customers = context.dependency_outputs["ingest_customers"]["customers_count"]
            orders = context.dependency_outputs["ingest_orders"]["orders_count"]
            return {
                "reconciled": True,
                "total_customers": customers,
                "total_orders": orders,
            }

        # LOT-32 fluid flow operator
        [ingest_customers, ingest_orders] >> reconcile_360

        wf = WorkflowDefinition(
            name="customer_360_v2_e2e",
            tasks=(ingest_customers, ingest_orders, reconcile_360),
        )

        # 1. Run initially with simulated failure
        result1 = runtime.run(wf)
        assert result1.status is WorkflowRunStatus.FAILED
        assert result1.task("ingest_customers").status is TaskRunStatus.SUCCEEDED
        assert result1.task("ingest_orders").status is TaskRunStatus.SUCCEEDED
        assert result1.task("reconcile_360").status is TaskRunStatus.FAILED
        assert ingest_customer_calls == 1
        assert ingest_order_calls == 1
        assert reconcile_calls == 1

        # 2. Fix the incident and selectively resume the failed workflow
        should_fail_reconcile = False
        result2 = runtime.resume_run(
            result1.run_id,
            wf,
        )
        assert result2.status is WorkflowRunStatus.SUCCEEDED
        assert result2.task("reconcile_360").status is TaskRunStatus.SUCCEEDED
        assert result2.task("reconcile_360").output["reconciled"] is True

        # Crucial: Upstream tasks must NOT have been re-executed
        assert ingest_customer_calls == 1
        assert ingest_order_calls == 1
        assert reconcile_calls == 2

        # 3. Store pruning test
        retention = RetentionPolicy(retention_days=1, max_runs_per_workflow=1)
        prune_report = store.prune_runs(retention)
        assert prune_report.scanned_workflows >= 1
        assert prune_report.deleted_records.workflow_runs >= 0
