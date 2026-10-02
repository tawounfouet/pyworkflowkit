"""LOT-04 attempt numbering and retry-identity invariants."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit.errors import RuntimeInvariantError
from pyworkflowkit.runtime import (
    TaskAttemptId,
    TaskRun,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.runtime._attempts import next_task_attempt
from pyworkflowkit.states import (
    TaskAttemptStateMachine,
    TaskAttemptStatus,
    TaskRunStateMachine,
    TaskRunStatus,
)

T0 = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _task_run() -> TaskRun:
    task = TaskRun(
        task_run_id=TaskRunId.parse("TR-1"),
        workflow_run_id=WorkflowRunId.parse("W-1"),
        task_key="fetch",
        created_at=T0,
    )
    TaskRunStateMachine().transition(task, TaskRunStatus.READY, at=T0)
    return task


def test_retry_keeps_task_run_id_and_creates_new_attempt_id() -> None:
    task = _task_run()
    task_machine = TaskRunStateMachine()
    attempt_machine = TaskAttemptStateMachine()

    task_machine.transition(task, TaskRunStatus.RUNNING, at=T0)

    first = next_task_attempt(
        task,
        (),
        attempt_id=TaskAttemptId.parse("TA-1"),
        created_at=T0,
    )
    attempt_machine.transition(first, TaskAttemptStatus.STARTING, at=T0)
    attempt_machine.transition(
        first,
        TaskAttemptStatus.RUNNING,
        at=T0 + timedelta(seconds=1),
    )
    attempt_machine.transition(
        first,
        TaskAttemptStatus.FAILED,
        at=T0 + timedelta(seconds=2),
    )

    second = next_task_attempt(
        task,
        (first,),
        attempt_id=TaskAttemptId.parse("TA-2"),
        created_at=T0 + timedelta(seconds=3),
    )

    assert first.task_run_id == task.task_run_id
    assert second.task_run_id == task.task_run_id
    assert first.attempt_id != second.attempt_id
    assert first.attempt_number == 1
    assert second.attempt_number == 2


def test_new_attempt_is_forbidden_after_success() -> None:
    task = _task_run()
    TaskRunStateMachine().transition(task, TaskRunStatus.RUNNING, at=T0)

    first = next_task_attempt(
        task,
        (),
        attempt_id=TaskAttemptId.parse("TA-1"),
        created_at=T0,
    )
    machine = TaskAttemptStateMachine()
    machine.transition(first, TaskAttemptStatus.STARTING, at=T0)
    machine.transition(first, TaskAttemptStatus.RUNNING, at=T0)
    machine.transition(first, TaskAttemptStatus.SUCCEEDED, at=T0)

    with pytest.raises(RuntimeInvariantError, match="FAILED or TIMED_OUT"):
        next_task_attempt(
            task,
            (first,),
            attempt_id=TaskAttemptId.parse("TA-2"),
            created_at=T0,
        )


def test_unknown_outcome_cannot_be_blindly_retried() -> None:
    task = _task_run()
    TaskRunStateMachine().transition(task, TaskRunStatus.RUNNING, at=T0)

    first = next_task_attempt(
        task,
        (),
        attempt_id=TaskAttemptId.parse("TA-1"),
        created_at=T0,
    )
    machine = TaskAttemptStateMachine()
    machine.transition(first, TaskAttemptStatus.STARTING, at=T0)
    machine.transition(first, TaskAttemptStatus.RUNNING, at=T0)
    machine.transition(first, TaskAttemptStatus.UNKNOWN_OUTCOME, at=T0)

    with pytest.raises(RuntimeInvariantError, match="FAILED or TIMED_OUT"):
        next_task_attempt(
            task,
            (first,),
            attempt_id=TaskAttemptId.parse("TA-2"),
            created_at=T0,
        )


def test_attempt_sequence_requires_contiguous_numbers() -> None:
    task = _task_run()
    TaskRunStateMachine().transition(task, TaskRunStatus.RUNNING, at=T0)

    from pyworkflowkit.runtime import TaskAttempt

    invalid = TaskAttempt(
        attempt_id=TaskAttemptId.parse("TA-2"),
        task_run_id=task.task_run_id,
        attempt_number=2,
        created_at=T0,
        _status=TaskAttemptStatus.FAILED,
        ended_at=T0,
    )

    with pytest.raises(RuntimeInvariantError, match="contiguous"):
        next_task_attempt(
            task,
            (invalid,),
            attempt_id=TaskAttemptId.parse("TA-3"),
            created_at=T0,
        )
