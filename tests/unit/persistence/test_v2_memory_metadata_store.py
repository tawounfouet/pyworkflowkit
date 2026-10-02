"""Focused LOT-05 unit tests for InMemoryMetadataStore."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pyworkflowkit.errors import MetadataInvariantError, MetadataNotFoundError
from pyworkflowkit.persistence import (
    InMemoryMetadataStore,
    StateEntityType,
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

NOW = datetime(2026, 10, 2, 14, 0, tzinfo=UTC)


def _workflow() -> WorkflowRun:
    return WorkflowRun(
        run_id=WorkflowRunId.parse("W-1"),
        workflow_name="demo",
        workflow_version="1",
        definition_fingerprint="sha256:def",
        plan_fingerprint="sha256:plan",
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-1"),
        ),
        created_at=NOW,
    )


def test_metadata_declares_memory_capabilities_truthfully() -> None:
    metadata = InMemoryMetadataStore().metadata()

    assert metadata.contract_version == "1"
    assert metadata.schema_version == "1"
    assert metadata.durable is False
    assert metadata.supports_concurrent_writers is True
    assert metadata.supports_atomic_batch is False


def test_missing_entities_fail_explicitly() -> None:
    store = InMemoryMetadataStore()

    with pytest.raises(MetadataNotFoundError):
        store.get_workflow_run(WorkflowRunId.parse("missing"))
    with pytest.raises(MetadataNotFoundError):
        store.get_task_run(TaskRunId.parse("missing"))
    with pytest.raises(MetadataNotFoundError):
        store.get_task_attempt(TaskAttemptId.parse("missing"))


def test_status_change_requires_transition_timestamp() -> None:
    store = InMemoryMetadataStore()
    run = _workflow()
    store.create_workflow_run(run)

    changed = store.get_workflow_run(run.run_id)
    changed._apply_status(WorkflowRunStatus.RUNNING, started_at=NOW)

    with pytest.raises(MetadataInvariantError, match="transitioned_at"):
        store.update_workflow_run(
            changed,
            expected_status=WorkflowRunStatus.PENDING,
        )


def test_task_attempt_requires_existing_task_run() -> None:
    store = InMemoryMetadataStore()
    attempt = TaskAttempt(
        attempt_id=TaskAttemptId.parse("TA-1"),
        task_run_id=TaskRunId.parse("TR-1"),
        attempt_number=1,
        created_at=NOW,
    )

    with pytest.raises(MetadataNotFoundError):
        store.append_task_attempt(attempt)


def test_state_history_global_sequence_is_deterministic() -> None:
    store = InMemoryMetadataStore()
    run = _workflow()
    store.create_workflow_run(run)

    task = TaskRun(
        task_run_id=TaskRunId.parse("TR-1"),
        workflow_run_id=run.run_id,
        task_key="fetch",
        created_at=NOW,
    )
    store.create_task_run(task)

    attempt = TaskAttempt(
        attempt_id=TaskAttemptId.parse("TA-1"),
        task_run_id=task.task_run_id,
        attempt_number=1,
        created_at=NOW,
    )
    store.append_task_attempt(attempt)

    history = store.list_state_transitions()
    assert tuple(record.sequence for record in history) == (1, 2, 3)
    assert tuple(record.entity_type for record in history) == (
        StateEntityType.WORKFLOW_RUN,
        StateEntityType.TASK_RUN,
        StateEntityType.TASK_ATTEMPT,
    )


def test_new_entity_must_enter_persistence_in_pending_state() -> None:
    store = InMemoryMetadataStore()
    run = _workflow()
    run._apply_status(WorkflowRunStatus.RUNNING, started_at=NOW)

    with pytest.raises(MetadataInvariantError, match="must begin in PENDING"):
        store.create_workflow_run(run)
