"""Unit tests for retention policy validation and InMemoryMetadataStore pruning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from pyworkflowkit.persistence.memory import InMemoryMetadataStore
from pyworkflowkit.persistence.retention import (
    DeletedRecordsSummary,
    PruneReport,
    RetentionPolicy,
)
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    TaskAttempt,
    TaskAttemptId,
    TaskRun,
    TaskRunId,
    WorkflowRun,
    WorkflowRunId,
)
from pyworkflowkit.states import WorkflowRunStatus

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def _create_run(
    store: InMemoryMetadataStore,
    run_id_str: str,
    workflow_name: str = "flow-a",
    created_at: datetime = NOW,
    final_status: WorkflowRunStatus = WorkflowRunStatus.SUCCEEDED,
    with_child_entities: bool = False,
) -> WorkflowRun:
    run_id = WorkflowRunId.parse(run_id_str)
    run = WorkflowRun(
        run_id=run_id,
        workflow_name=workflow_name,
        workflow_version="1.0",
        definition_fingerprint="sha256:def",
        plan_fingerprint="sha256:plan",
        correlation=CorrelationContext(correlation_id=CorrelationId.parse("C-1")),
        created_at=created_at,
    )
    store.create_workflow_run(run)

    if with_child_entities:
        task_id = TaskRunId.parse(f"TR-{run_id_str}")
        task_run = TaskRun(
            task_run_id=task_id,
            workflow_run_id=run_id,
            task_key="step-1",
            created_at=created_at,
        )
        store.create_task_run(task_run)

        attempt = TaskAttempt(
            attempt_id=TaskAttemptId.parse(f"TA-{run_id_str}"),
            task_run_id=task_id,
            attempt_number=1,
            created_at=created_at,
        )
        store.append_task_attempt(attempt)

    if final_status != WorkflowRunStatus.PENDING:
        t1 = created_at + timedelta(seconds=1)
        run._apply_status(WorkflowRunStatus.RUNNING, started_at=t1)
        store.update_workflow_run(
            run,
            expected_status=WorkflowRunStatus.PENDING,
            transitioned_at=t1,
        )

        if final_status != WorkflowRunStatus.RUNNING:
            t2 = created_at + timedelta(seconds=2)
            run._apply_status(final_status, ended_at=t2)
            store.update_workflow_run(
                run,
                expected_status=WorkflowRunStatus.RUNNING,
                transitioned_at=t2,
            )

    return run


# --- RetentionPolicy Model Tests ---


def test_retention_policy_defaults_and_immutability() -> None:
    policy = RetentionPolicy()
    assert policy.retention_days == 30
    assert policy.max_runs_per_workflow == 100
    assert policy.retain_failed_runs_days == 90
    assert policy.workflow_names is None
    assert set(policy.prune_states) == {
        WorkflowRunStatus.SUCCEEDED,
        WorkflowRunStatus.CANCELLED,
    }

    with pytest.raises(ValidationError):
        policy.retention_days = 10  # type: ignore[misc]


def test_retention_policy_validations() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        RetentionPolicy(retention_days=0)

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        RetentionPolicy(max_runs_per_workflow=0)

    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        RetentionPolicy(retain_failed_runs_days=0)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        RetentionPolicy(unknown_param="foo")  # type: ignore[call-arg]

    with pytest.raises(ValidationError, match="prune_states must not be empty"):
        RetentionPolicy(prune_states=[])

    with pytest.raises(ValidationError, match="Only terminal workflow statuses can be pruned"):
        RetentionPolicy(prune_states=[WorkflowRunStatus.RUNNING])

    with pytest.raises(ValidationError, match="Only terminal workflow statuses can be pruned"):
        RetentionPolicy(prune_states=[WorkflowRunStatus.PENDING])

    with pytest.raises(ValidationError, match="Input should be"):
        RetentionPolicy(prune_states=["INVALID_STRING"])  # type: ignore[list-item]


def test_deleted_records_summary_and_prune_report() -> None:
    summary = DeletedRecordsSummary(
        workflow_runs=2,
        task_runs=4,
        task_attempts=4,
        events=8,
        checkpoints=2,
        external_refs=0,
        manifests=1,
    )
    d = summary.to_dict()
    assert d["workflow_runs"] == 2
    assert d["task_runs"] == 4

    report_dry = PruneReport(
        dry_run=True,
        scanned_workflows=3,
        eligible_runs_to_prune=2,
        deleted_records=summary,
    )
    assert report_dry.estimated_deleted_records == summary
    dry_dict = report_dry.to_dict()
    assert dry_dict["dry_run"] is True
    assert "estimated_deleted_records" in dry_dict
    assert "deleted_records" not in dry_dict

    report_real = PruneReport(
        dry_run=False,
        scanned_workflows=3,
        eligible_runs_to_prune=2,
        deleted_records=summary,
    )
    real_dict = report_real.to_dict()
    assert real_dict["dry_run"] is False
    assert "deleted_records" in real_dict
    assert "estimated_deleted_records" not in real_dict


# --- InMemoryMetadataStore Pruning Tests ---


def test_in_memory_prune_by_age() -> None:
    store = InMemoryMetadataStore()
    # 40 days old (should be pruned with retention_days=30)
    _create_run(store, "W-OLD", created_at=NOW - timedelta(days=40))
    # 10 days old (should be kept)
    _create_run(store, "W-NEW", created_at=NOW - timedelta(days=10))
    # 50 days old but RUNNING (should never be pruned)
    _create_run(
        store,
        "W-RUNNING",
        created_at=NOW - timedelta(days=50),
        final_status=WorkflowRunStatus.RUNNING,
    )

    policy = RetentionPolicy(retention_days=30, max_runs_per_workflow=None)
    report = store.prune_runs(policy, dry_run=False)

    assert report.eligible_runs_to_prune == 1
    assert report.deleted_records.workflow_runs == 1

    remaining = [str(r.run_id) for r in store.list_workflow_runs()]
    assert "W-OLD" not in remaining
    assert "W-NEW" in remaining
    assert "W-RUNNING" in remaining


def test_in_memory_prune_dry_run_does_not_delete() -> None:
    store = InMemoryMetadataStore()
    _create_run(store, "W-OLD", created_at=NOW - timedelta(days=40), with_child_entities=True)

    policy = RetentionPolicy(retention_days=30, max_runs_per_workflow=None)
    report = store.prune_runs(policy, dry_run=True)

    assert report.dry_run is True
    assert report.eligible_runs_to_prune == 1
    assert report.deleted_records.workflow_runs == 1
    assert report.deleted_records.task_runs == 1
    assert report.deleted_records.task_attempts == 1

    # Verify everything still exists in store
    assert len(store.list_workflow_runs()) == 1
    assert len(store.list_task_runs(WorkflowRunId.parse("W-OLD"))) == 1


def test_in_memory_prune_by_workflow_quota() -> None:
    store = InMemoryMetadataStore()
    # Create 4 completed runs for flow-a
    _create_run(store, "W-1", workflow_name="flow-a", created_at=NOW - timedelta(days=4))
    _create_run(store, "W-2", workflow_name="flow-a", created_at=NOW - timedelta(days=3))
    _create_run(store, "W-3", workflow_name="flow-a", created_at=NOW - timedelta(days=2))
    _create_run(store, "W-4", workflow_name="flow-a", created_at=NOW - timedelta(days=1))

    # Keep only 2 most recent runs per workflow
    policy = RetentionPolicy(retention_days=None, max_runs_per_workflow=2)
    report = store.prune_runs(policy, dry_run=False)

    assert report.eligible_runs_to_prune == 2
    assert report.deleted_records.workflow_runs == 2

    remaining = [str(r.run_id) for r in store.list_workflow_runs()]
    assert set(remaining) == {"W-3", "W-4"}


def test_in_memory_prune_retain_failed_runs_extended_window() -> None:
    store = InMemoryMetadataStore()
    # 20 days old SUCCEEDED run -> eligible with retention_days=15
    _create_run(
        store,
        "W-SUCC",
        created_at=NOW - timedelta(days=20),
        final_status=WorkflowRunStatus.SUCCEEDED,
    )
    # 20 days old FAILED run -> retained because 20 < 40 days
    _create_run(
        store,
        "W-FAIL-RECENT",
        created_at=NOW - timedelta(days=20),
        final_status=WorkflowRunStatus.FAILED,
    )
    # 50 days old FAILED run -> eligible because 50 > 40 days
    _create_run(
        store,
        "W-FAIL-OLD",
        created_at=NOW - timedelta(days=50),
        final_status=WorkflowRunStatus.FAILED,
    )

    policy = RetentionPolicy(
        retention_days=15,
        max_runs_per_workflow=None,
        retain_failed_runs_days=40,
        prune_states=(WorkflowRunStatus.SUCCEEDED, WorkflowRunStatus.FAILED),
    )
    report = store.prune_runs(policy, dry_run=False)

    assert report.eligible_runs_to_prune == 2
    assert report.deleted_records.workflow_runs == 2

    remaining = [str(r.run_id) for r in store.list_workflow_runs()]
    assert "W-SUCC" not in remaining
    assert "W-FAIL-OLD" not in remaining
    assert "W-FAIL-RECENT" in remaining


def test_in_memory_prune_filters_workflow_names() -> None:
    store = InMemoryMetadataStore()
    _create_run(store, "W-A", workflow_name="target-flow", created_at=NOW - timedelta(days=40))
    _create_run(store, "W-B", workflow_name="other-flow", created_at=NOW - timedelta(days=40))

    policy = RetentionPolicy(
        retention_days=30,
        max_runs_per_workflow=None,
        workflow_names=("target-flow",),
    )
    report = store.prune_runs(policy, dry_run=False)

    assert report.eligible_runs_to_prune == 1
    assert report.deleted_records.workflow_runs == 1

    remaining = [str(r.run_id) for r in store.list_workflow_runs()]
    assert "W-A" not in remaining
    assert "W-B" in remaining


def test_in_memory_cascade_deletion_cleans_transitions_and_attempts() -> None:
    store = InMemoryMetadataStore()
    _create_run(store, "W-DEL", created_at=NOW - timedelta(days=40), with_child_entities=True)
    _create_run(store, "W-KEEP", created_at=NOW - timedelta(days=5), with_child_entities=True)

    initial_transitions = len(store.list_state_transitions())
    assert initial_transitions > 0

    policy = RetentionPolicy(retention_days=30, max_runs_per_workflow=None)
    report = store.prune_runs(policy, dry_run=False)

    assert report.deleted_records.workflow_runs == 1
    assert report.deleted_records.task_runs == 1
    assert report.deleted_records.task_attempts == 1

    # Deleted entities transitions must be gone
    remaining_transitions = store.list_state_transitions()
    for t in remaining_transitions:
        assert "W-DEL" not in t.entity_id
        assert "TR-W-DEL" not in t.entity_id
        assert "TA-W-DEL" not in t.entity_id
