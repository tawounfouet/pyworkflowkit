"""LOT-04 unit tests for canonical V2 runtime entities."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

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
from pyworkflowkit.states import (
    BlockReason,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)


NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _workflow_run(**overrides: object) -> WorkflowRun:
    values: dict[str, object] = {
        "run_id": WorkflowRunId.parse("W-1"),
        "workflow_name": "demo",
        "workflow_version": "1",
        "definition_fingerprint": "sha256:def",
        "plan_fingerprint": "sha256:plan",
        "correlation": CorrelationContext(
            correlation_id=CorrelationId.parse("C-1"),
        ),
        "created_at": NOW,
    }
    values.update(overrides)
    return WorkflowRun(**values)  # type: ignore[arg-type]


def _task_run(**overrides: object) -> TaskRun:
    values: dict[str, object] = {
        "task_run_id": TaskRunId.parse("TR-1"),
        "workflow_run_id": WorkflowRunId.parse("W-1"),
        "task_key": "fetch",
        "created_at": NOW,
    }
    values.update(overrides)
    return TaskRun(**values)  # type: ignore[arg-type]


def _attempt(**overrides: object) -> TaskAttempt:
    values: dict[str, object] = {
        "attempt_id": TaskAttemptId.parse("TA-1"),
        "task_run_id": TaskRunId.parse("TR-1"),
        "attempt_number": 1,
        "created_at": NOW,
    }
    values.update(overrides)
    return TaskAttempt(**values)  # type: ignore[arg-type]


def test_runtime_entities_use_v2_typed_identity() -> None:
    workflow = _workflow_run()
    task = _task_run()
    attempt = _attempt()

    assert type(workflow.run_id) is WorkflowRunId
    assert type(task.task_run_id) is TaskRunId
    assert type(task.workflow_run_id) is WorkflowRunId
    assert type(attempt.attempt_id) is TaskAttemptId
    assert type(attempt.task_run_id) is TaskRunId


def test_status_is_read_only_through_public_property() -> None:
    workflow = _workflow_run()
    task = _task_run()
    attempt = _attempt()

    with pytest.raises(AttributeError):
        workflow.status = WorkflowRunStatus.RUNNING  # type: ignore[misc]
    with pytest.raises(AttributeError):
        task.status = TaskRunStatus.READY  # type: ignore[misc]
    with pytest.raises(AttributeError):
        attempt.status = TaskAttemptStatus.STARTING  # type: ignore[misc]


def test_terminal_workflow_snapshot_requires_ended_at() -> None:
    with pytest.raises(ValueError, match="terminal WorkflowRun"):
        _workflow_run(_status=WorkflowRunStatus.SUCCEEDED)


def test_skipped_task_snapshot_requires_reason() -> None:
    with pytest.raises(ValueError, match="requires skip_reason"):
        _task_run(
            _status=TaskRunStatus.SKIPPED,
            ended_at=NOW,
        )

    task = _task_run(
        _status=TaskRunStatus.SKIPPED,
        skip_reason=SkipReason.CONDITION_FALSE,
        ended_at=NOW,
    )
    assert task.skip_reason is SkipReason.CONDITION_FALSE


def test_blocked_task_snapshot_requires_reason_and_is_non_terminal() -> None:
    with pytest.raises(ValueError, match="requires block_reason"):
        _task_run(_status=TaskRunStatus.BLOCKED)

    task = _task_run(
        _status=TaskRunStatus.BLOCKED,
        block_reason=BlockReason.UPSTREAM_UNKNOWN,
    )
    assert task.status is TaskRunStatus.BLOCKED
    assert task.ended_at is None


def test_terminal_attempt_snapshot_requires_ended_at() -> None:
    with pytest.raises(ValueError, match="terminal TaskAttempt"):
        _attempt(_status=TaskAttemptStatus.FAILED)


def test_runtime_timestamps_must_be_timezone_aware() -> None:
    naive = datetime(2026, 10, 2, 12, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        _workflow_run(created_at=naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        _task_run(created_at=naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        _attempt(created_at=naive)
