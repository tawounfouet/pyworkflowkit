"""LOT-04 unit tests for explicit V2 state machines."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit.errors import InvalidStateTransitionError, TerminalStateError
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
    TaskAttemptStateMachine,
    TaskAttemptStatus,
    TaskRunStateMachine,
    TaskRunStatus,
    WorkflowRunStateMachine,
    WorkflowRunStatus,
)

T0 = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
T1 = T0 + timedelta(seconds=1)
T2 = T0 + timedelta(seconds=2)
T3 = T0 + timedelta(seconds=3)
T4 = T0 + timedelta(seconds=4)
T5 = T0 + timedelta(seconds=5)
T6 = T0 + timedelta(seconds=6)


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
        created_at=T0,
    )


def _task() -> TaskRun:
    return TaskRun(
        task_run_id=TaskRunId.parse("TR-1"),
        workflow_run_id=WorkflowRunId.parse("W-1"),
        task_key="fetch",
        created_at=T0,
    )


def _attempt() -> TaskAttempt:
    return TaskAttempt(
        attempt_id=TaskAttemptId.parse("TA-1"),
        task_run_id=TaskRunId.parse("TR-1"),
        attempt_number=1,
        created_at=T0,
    )


def test_workflow_happy_path_and_terminal_protection() -> None:
    run = _workflow()
    machine = WorkflowRunStateMachine()

    machine.transition(run, WorkflowRunStatus.RUNNING, at=T1)
    machine.transition(run, WorkflowRunStatus.SUCCEEDED, at=T2)

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert run.started_at == T1
    assert run.ended_at == T2

    with pytest.raises(TerminalStateError):
        machine.transition(run, WorkflowRunStatus.FAILED, at=T3)


def test_workflow_cancellation_request_is_distinct_from_confirmation() -> None:
    run = _workflow()
    machine = WorkflowRunStateMachine()

    machine.transition(run, WorkflowRunStatus.RUNNING, at=T1)
    machine.transition(run, WorkflowRunStatus.CANCELLATION_REQUESTED, at=T2)

    assert run.status is WorkflowRunStatus.CANCELLATION_REQUESTED
    assert run.ended_at is None

    machine.transition(run, WorkflowRunStatus.CANCELLED, at=T3)

    assert run.status is WorkflowRunStatus.CANCELLED
    assert run.ended_at == T3


def test_workflow_unknown_outcome_can_be_reconciled_to_terminal_truth() -> None:
    run = _workflow()
    machine = WorkflowRunStateMachine()

    machine.transition(run, WorkflowRunStatus.RUNNING, at=T1)
    machine.transition(run, WorkflowRunStatus.UNKNOWN_OUTCOME, at=T2)
    machine.transition(run, WorkflowRunStatus.SUCCEEDED, at=T3)

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert run.ended_at == T3


def test_task_blocked_state_can_return_to_ready() -> None:
    task = _task()
    machine = TaskRunStateMachine()

    machine.transition(
        task,
        TaskRunStatus.BLOCKED,
        at=T1,
        block_reason=BlockReason.UPSTREAM_UNKNOWN,
    )
    assert task.status is TaskRunStatus.BLOCKED
    assert task.block_reason is BlockReason.UPSTREAM_UNKNOWN

    machine.transition(task, TaskRunStatus.READY, at=T2)

    assert task.status is TaskRunStatus.READY
    assert task.block_reason is None


def test_task_skip_requires_reason_and_is_terminal() -> None:
    task = _task()
    machine = TaskRunStateMachine()

    with pytest.raises(ValueError, match="skip_reason"):
        machine.transition(task, TaskRunStatus.SKIPPED, at=T1)

    machine.transition(
        task,
        TaskRunStatus.SKIPPED,
        at=T1,
        skip_reason=SkipReason.TRIGGER_RULE_UNSATISFIED,
    )

    assert task.status is TaskRunStatus.SKIPPED
    assert task.ended_at == T1

    with pytest.raises(TerminalStateError):
        machine.transition(task, TaskRunStatus.READY, at=T2)


def test_task_run_happy_path_records_start_and_end() -> None:
    task = _task()
    machine = TaskRunStateMachine()

    machine.transition(task, TaskRunStatus.READY, at=T1)
    machine.transition(task, TaskRunStatus.RUNNING, at=T2)
    machine.transition(task, TaskRunStatus.SUCCEEDED, at=T3)

    assert task.started_at == T2
    assert task.ended_at == T3


def test_attempt_preserves_cancellation_uncertainty_until_reconciliation() -> None:
    attempt = _attempt()
    machine = TaskAttemptStateMachine()

    machine.transition(attempt, TaskAttemptStatus.STARTING, at=T1)
    machine.transition(attempt, TaskAttemptStatus.RUNNING, at=T2)
    machine.transition(attempt, TaskAttemptStatus.CANCELLATION_REQUESTED, at=T3)
    machine.transition(attempt, TaskAttemptStatus.CANCELLATION_UNCONFIRMED, at=T4)
    machine.transition(attempt, TaskAttemptStatus.REQUIRES_RECONCILIATION, at=T5)

    assert attempt.status is TaskAttemptStatus.REQUIRES_RECONCILIATION
    assert attempt.ended_at is None

    machine.transition(attempt, TaskAttemptStatus.CANCELLED, at=T6)

    assert attempt.status is TaskAttemptStatus.CANCELLED
    assert attempt.ended_at == T6


def test_attempt_unknown_outcome_does_not_become_failure_implicitly() -> None:
    attempt = _attempt()
    machine = TaskAttemptStateMachine()

    machine.transition(attempt, TaskAttemptStatus.STARTING, at=T1)
    machine.transition(attempt, TaskAttemptStatus.RUNNING, at=T2)
    machine.transition(attempt, TaskAttemptStatus.UNKNOWN_OUTCOME, at=T3)

    assert attempt.status is TaskAttemptStatus.UNKNOWN_OUTCOME
    assert attempt.ended_at is None

    machine.transition(attempt, TaskAttemptStatus.REQUIRES_RECONCILIATION, at=T4)
    machine.transition(attempt, TaskAttemptStatus.SUCCEEDED, at=T5)

    assert attempt.status is TaskAttemptStatus.SUCCEEDED


def test_invalid_nonterminal_transition_fails_explicitly() -> None:
    attempt = _attempt()

    with pytest.raises(InvalidStateTransitionError):
        TaskAttemptStateMachine().transition(
            attempt,
            TaskAttemptStatus.SUCCEEDED,
            at=T1,
        )


def test_transition_timestamps_must_be_timezone_aware() -> None:
    naive = datetime(2026, 10, 2, 12, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        WorkflowRunStateMachine().transition(
            _workflow(),
            WorkflowRunStatus.RUNNING,
            at=naive,
        )



def test_unknown_outcome_can_be_reconciled_to_known_timeout() -> None:
    run = _workflow()
    task = _task()

    workflow_machine = WorkflowRunStateMachine()
    task_machine = TaskRunStateMachine()

    workflow_machine.transition(run, WorkflowRunStatus.RUNNING, at=T1)
    workflow_machine.transition(run, WorkflowRunStatus.UNKNOWN_OUTCOME, at=T2)
    workflow_machine.transition(run, WorkflowRunStatus.TIMED_OUT, at=T3)

    task_machine.transition(task, TaskRunStatus.READY, at=T1)
    task_machine.transition(task, TaskRunStatus.RUNNING, at=T2)
    task_machine.transition(task, TaskRunStatus.UNKNOWN_OUTCOME, at=T3)
    task_machine.transition(task, TaskRunStatus.TIMED_OUT, at=T4)

    assert run.status is WorkflowRunStatus.TIMED_OUT
    assert task.status is TaskRunStatus.TIMED_OUT
