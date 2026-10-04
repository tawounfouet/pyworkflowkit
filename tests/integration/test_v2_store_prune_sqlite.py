"""Integration tests for SQLiteMetadataStore lifecycle pruning, batching, and integrity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import text

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.persistence import SQLiteMetadataStore
from pyworkflowkit.persistence.retention import RetentionPolicy
from pyworkflowkit.runtime import WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def test_sqlite_prune_cascade_batching_and_integrity(tmp_path: Path) -> None:
    database = tmp_path / "prune_test.sqlite3"

    workflow_alpha = WorkflowDefinition(
        name="workflow-alpha",
        tasks=(
            TaskDefinition(key="task-1", workload=lambda: {"rows": 10}),
            TaskDefinition(
                key="task-2",
                workload=lambda: {"status": "ok"},
                dependencies=("task-1",),
            ),
        ),
    )
    workflow_beta = WorkflowDefinition(
        name="workflow-beta",
        tasks=(TaskDefinition(key="task-single", workload=lambda: {"done": True}),),
    )

    run_ids_alpha: list[str] = []
    run_ids_beta: list[str] = []

    with SQLiteMetadataStore(database, wal=False) as store:
        runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)

        # Generate 3 runs for alpha
        for _ in range(3):
            res = runtime.run(workflow_alpha)
            assert res.status is WorkflowRunStatus.SUCCEEDED
            run_ids_alpha.append(str(res.run_id))

        # Generate 2 runs for beta
        for _ in range(2):
            res = runtime.run(workflow_beta)
            assert res.status is WorkflowRunStatus.SUCCEEDED
            run_ids_beta.append(str(res.run_id))

        # Backdate runs directly in SQLite:
        # alpha[0] -> 50 days ago (old)
        # alpha[1] -> 40 days ago (old)
        # alpha[2] -> 5 days ago (recent)
        # beta[0] -> 45 days ago (old)
        # beta[1] -> 2 days ago (recent)
        date_50d = (NOW - timedelta(days=50)).isoformat()
        date_40d = (NOW - timedelta(days=40)).isoformat()
        date_5d = (NOW - timedelta(days=5)).isoformat()
        date_45d = (NOW - timedelta(days=45)).isoformat()
        date_2d = (NOW - timedelta(days=2)).isoformat()

        with store._session_factory() as session:
            session.execute(
                text("UPDATE v2_workflow_runs SET created_at = :dt WHERE run_id = :rid"),
                {"dt": date_50d, "rid": run_ids_alpha[0]},
            )
            session.execute(
                text("UPDATE v2_workflow_runs SET created_at = :dt WHERE run_id = :rid"),
                {"dt": date_40d, "rid": run_ids_alpha[1]},
            )
            session.execute(
                text("UPDATE v2_workflow_runs SET created_at = :dt WHERE run_id = :rid"),
                {"dt": date_5d, "rid": run_ids_alpha[2]},
            )
            session.execute(
                text("UPDATE v2_workflow_runs SET created_at = :dt WHERE run_id = :rid"),
                {"dt": date_45d, "rid": run_ids_beta[0]},
            )
            session.execute(
                text("UPDATE v2_workflow_runs SET created_at = :dt WHERE run_id = :rid"),
                {"dt": date_2d, "rid": run_ids_beta[1]},
            )
            session.commit()

        # Phase 1: Dry-Run simulation with retention_days=30
        policy_30d = RetentionPolicy(retention_days=30, max_runs_per_workflow=None)
        dry_report = store.prune_runs(policy_30d, dry_run=True)

        assert dry_report.dry_run is True
        assert dry_report.scanned_workflows >= 2
        # Eligible: alpha[0], alpha[1], beta[0] -> 3 runs
        assert dry_report.eligible_runs_to_prune == 3
        assert dry_report.estimated_deleted_records.workflow_runs == 3
        assert dry_report.estimated_deleted_records.task_runs == (2 + 2 + 1)  # 5 tasks
        assert dry_report.estimated_deleted_records.checkpoints > 0
        assert dry_report.estimated_deleted_records.events > 0

        # Verify nothing was deleted after dry run
        all_runs_before = store.list_workflow_runs()
        assert len(all_runs_before) == 5

        # Phase 2: Real execution with batch_size=2 to test chunked transactions
        real_report = store.prune_runs(policy_30d, dry_run=False, batch_size=2)

        assert real_report.dry_run is False
        assert real_report.eligible_runs_to_prune == 3
        assert real_report.deleted_records.workflow_runs == 3
        assert real_report.deleted_records.task_runs == 5

        # Verify surviving runs
        remaining_run_ids = {str(r.run_id) for r in store.list_workflow_runs()}
        assert remaining_run_ids == {run_ids_alpha[2], run_ids_beta[1]}

        # Phase 3: Integrity verification on SQLite
        with store._session_factory() as session:
            fk_violations = session.execute(text("PRAGMA foreign_key_check")).fetchall()
            assert fk_violations == [], f"Foreign key violations found: {fk_violations}"

            integrity_status = session.execute(text("PRAGMA integrity_check")).scalar()
            assert integrity_status == "ok", f"Integrity check failed: {integrity_status}"

    # Phase 4: Re-open store and verify reading survivors
    with SQLiteMetadataStore(database, wal=False) as reopened:
        reopened_runs = reopened.list_workflow_runs()
        assert len(reopened_runs) == 2

        for r in reopened_runs:
            tasks = reopened.list_task_runs(r.run_id)
            assert len(tasks) > 0
            events = reopened.list_runtime_events(r.run_id)
            assert len(events) > 0


def test_sqlite_prune_quota_per_workflow(tmp_path: Path) -> None:
    database = tmp_path / "prune_quota.sqlite3"

    workflow = WorkflowDefinition(
        name="quota-flow",
        tasks=(TaskDefinition(key="step", workload=lambda: {"res": 1}),),
    )

    with SQLiteMetadataStore(database, wal=False) as store:
        runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
        run_ids: list[str] = []
        for _ in range(4):
            res = runtime.run(workflow)
            run_ids.append(str(res.run_id))

        # Adjust created_at so they are strictly sequential
        with store._session_factory() as session:
            for idx, rid in enumerate(run_ids):
                dt = (NOW - timedelta(minutes=10 - idx)).isoformat()
                session.execute(
                    text("UPDATE v2_workflow_runs SET created_at = :dt WHERE run_id = :rid"),
                    {"dt": dt, "rid": rid},
                )
            session.commit()

        # Keep only 2 most recent runs
        policy = RetentionPolicy(retention_days=None, max_runs_per_workflow=2)
        report = store.prune_runs(policy, dry_run=False)

        assert report.eligible_runs_to_prune == 2
        assert report.deleted_records.workflow_runs == 2

        survivors = {str(r.run_id) for r in store.list_workflow_runs()}
        # The 2 newest: run_ids[2] and run_ids[3]
        assert survivors == {run_ids[2], run_ids[3]}


def test_sqlite_prune_workflow_filter_and_failed_runs_extension(tmp_path: Path) -> None:
    database = tmp_path / "prune_filter_failed.sqlite3"

    flow_target = WorkflowDefinition(
        name="target-flow",
        tasks=(TaskDefinition(key="step", workload=lambda: {"res": 1}),),
    )
    flow_other = WorkflowDefinition(
        name="other-flow",
        tasks=(TaskDefinition(key="step", workload=lambda: {"res": 2}),),
    )

    with SQLiteMetadataStore(database, wal=False) as store:
        runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)

        res_succ = runtime.run(flow_target)
        res_fail = runtime.run(flow_target)
        res_other = runtime.run(flow_other)

        # Backdate runs:
        # res_succ -> 20 days ago, SUCCEEDED
        # res_fail -> 20 days ago, FAILED
        # res_other -> 20 days ago, SUCCEEDED
        dt_20d = (NOW - timedelta(days=20)).isoformat()
        with store._session_factory() as session:
            session.execute(
                text("UPDATE v2_workflow_runs SET created_at = :dt WHERE run_id = :rid"),
                {"dt": dt_20d, "rid": str(res_succ.run_id)},
            )
            session.execute(
                text(
                    "UPDATE v2_workflow_runs "
                    "SET created_at = :dt, status = 'FAILED' "
                    "WHERE run_id = :rid"
                ),
                {"dt": dt_20d, "rid": str(res_fail.run_id)},
            )

            session.execute(
                text("UPDATE v2_workflow_runs SET created_at = :dt WHERE run_id = :rid"),
                {"dt": dt_20d, "rid": str(res_other.run_id)},
            )
            session.commit()

        # Prune with retention_days=15, retain_failed_runs_days=30, restricted to target-flow
        policy = RetentionPolicy(
            retention_days=15,
            retain_failed_runs_days=30,
            workflow_names=("target-flow",),
            prune_states=(WorkflowRunStatus.SUCCEEDED, WorkflowRunStatus.FAILED),
        )
        report = store.prune_runs(policy, dry_run=False)

        # Only target-flow SUCCEEDED run should be pruned!
        # target-flow FAILED run is kept because 20 < 30 days
        # other-flow SUCCEEDED run is kept because it's not in workflow_names
        assert report.eligible_runs_to_prune == 1
        assert report.deleted_records.workflow_runs == 1

        survivors = {str(r.run_id) for r in store.list_workflow_runs()}
        assert str(res_succ.run_id) not in survivors
        assert str(res_fail.run_id) in survivors
        assert str(res_other.run_id) in survivors
