"""Tests for neutral persistence row mappings."""

from datetime import UTC, datetime

import pytest

from pyworkflowkit.adapters.persistence.mapping import PersistenceMapper
from pyworkflowkit.adapters.persistence.records import WorkflowRunRow
from pyworkflowkit.domain.enums import (
    RuntimeEventType,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import (
    ArtifactId,
    ExternalRunRefId,
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef
from pyworkflowkit.errors import SerializationError

NOW = datetime(2026, 9, 25, 20, 0, tzinfo=UTC)


def test_workflow_run_row_round_trip_hydrates_terminal_state_directly() -> None:
    run = WorkflowRun(
        run_id=WorkflowRunId("run-1"),
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
        status=WorkflowRunStatus.SUCCEEDED,
        parameters={"source": "input.csv"},
        created_at=NOW,
        started_at=NOW,
        finished_at=NOW,
    )

    row = PersistenceMapper.workflow_run_to_row(run)
    restored = PersistenceMapper.workflow_run_from_row(row)

    assert restored.status is WorkflowRunStatus.SUCCEEDED
    assert restored.finished_at == NOW
    assert restored.parameters == {"source": "input.csv"}
    assert row.status == "SUCCEEDED"


def test_task_run_row_preserves_skip_reason() -> None:
    task_run = TaskRun(
        task_run_id=TaskRunId("task-run-B"),
        run_id=WorkflowRunId("run-1"),
        task_id=TaskId("B"),
        status=TaskRunStatus.SKIPPED,
        skip_reason=SkipReason.DEPENDENCY_FAILED,
        created_at=NOW,
        finished_at=NOW,
    )

    restored = PersistenceMapper.task_run_from_row(PersistenceMapper.task_run_to_row(task_run))

    assert restored.status is TaskRunStatus.SKIPPED
    assert restored.skip_reason is SkipReason.DEPENDENCY_FAILED


def test_task_attempt_row_preserves_failure_evidence() -> None:
    attempt = TaskAttempt(
        attempt_id=TaskAttemptId("attempt-1"),
        task_run_id=TaskRunId("task-run-A"),
        attempt_number=1,
        status=TaskAttemptStatus.FAILED,
        started_at=NOW,
        finished_at=NOW,
        error_type="TimeoutError",
        error_message="temporary",
        error_category="TimeoutError",
        error_metadata={"provider": "remote"},
    )

    restored = PersistenceMapper.task_attempt_from_row(
        PersistenceMapper.task_attempt_to_row(attempt)
    )

    assert restored.status is TaskAttemptStatus.FAILED
    assert restored.error_type == "TimeoutError"
    assert restored.error_metadata == {"provider": "remote"}


def test_runtime_event_row_preserves_sequence() -> None:
    event = RuntimeEvent(
        event_id=RuntimeEventId("event-1"),
        event_type=RuntimeEventType.WORKFLOW_STARTED,
        run_id=WorkflowRunId("run-1"),
        occurred_at=NOW,
        event_sequence=1,
        payload={"source": "test"},
    )

    row = PersistenceMapper.runtime_event_to_row(event)
    restored = PersistenceMapper.runtime_event_from_row(row)

    assert row.event_sequence == 1
    assert restored == event


def test_artifact_row_preserves_task_ownership() -> None:
    artifact = ArtifactReference(
        artifact_id=ArtifactId("artifact-1"),
        name="output.csv",
        uri="file:///tmp/output.csv",
        metadata={"rows": 10},
    )

    row = PersistenceMapper.artifact_to_row(
        task_run_id=TaskRunId("task-run-A"),
        value=artifact,
    )
    owner, restored = PersistenceMapper.artifact_from_row(row)

    assert owner == TaskRunId("task-run-A")
    assert restored == artifact


def test_external_ref_row_preserves_task_ownership() -> None:
    external_ref = ExternalRunRef(
        external_ref_id=ExternalRunRefId("external-1"),
        provider="pyingestkit",
        external_run_id="job-42",
        metadata={"region": "eu"},
    )

    row = PersistenceMapper.external_ref_to_row(
        task_run_id=TaskRunId("task-run-A"),
        value=external_ref,
    )
    owner, restored = PersistenceMapper.external_ref_from_row(row)

    assert owner == TaskRunId("task-run-A")
    assert restored == external_ref


def test_row_hydration_normalizes_aware_datetime_to_utc() -> None:
    row = WorkflowRunRow(
        run_id="run-1",
        workflow_id="workflow",
        workflow_version="1",
        status="PENDING",
        parameters={},
        created_at=NOW,
        started_at=None,
        finished_at=None,
    )

    restored = PersistenceMapper.workflow_run_from_row(row)

    assert restored.created_at is not None
    assert restored.created_at.tzinfo is UTC


def test_row_mapping_rejects_non_portable_metadata() -> None:
    artifact = ArtifactReference(
        artifact_id=ArtifactId("artifact-1"),
        name="output.bin",
        uri="file:///tmp/output.bin",
        metadata={"bad": object()},
    )

    with pytest.raises(SerializationError):
        PersistenceMapper.artifact_to_row(
            task_run_id=TaskRunId("task-run-A"),
            value=artifact,
        )
