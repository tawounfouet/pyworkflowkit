"""LOT-04 property tests for terminal-state absorption."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pyworkflowkit.errors import TerminalStateError
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
    SkipReason,
    TaskAttemptStateMachine,
    TaskAttemptStatus,
    TaskRunStateMachine,
    TaskRunStatus,
    WorkflowRunStateMachine,
    WorkflowRunStatus,
)

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


@given(
    status=st.sampled_from(
        [
            WorkflowRunStatus.SUCCEEDED,
            WorkflowRunStatus.FAILED,
            WorkflowRunStatus.CANCELLED,
            WorkflowRunStatus.TIMED_OUT,
        ]
    ),
    target=st.sampled_from(list(WorkflowRunStatus)),
)
def test_terminal_workflow_states_are_absorbing(
    status: WorkflowRunStatus,
    target: WorkflowRunStatus,
) -> None:
    run = WorkflowRun(
        run_id=WorkflowRunId.parse("W-1"),
        workflow_name="demo",
        workflow_version="1",
        definition_fingerprint="sha256:def",
        plan_fingerprint="sha256:plan",
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-1"),
        ),
        created_at=NOW,
        _status=status,
        ended_at=NOW,
    )

    with pytest.raises(TerminalStateError):
        WorkflowRunStateMachine().transition(run, target, at=NOW)


@given(
    status=st.sampled_from(
        [
            TaskRunStatus.SUCCEEDED,
            TaskRunStatus.FAILED,
            TaskRunStatus.SKIPPED,
            TaskRunStatus.CANCELLED,
            TaskRunStatus.TIMED_OUT,
        ]
    ),
    target=st.sampled_from(list(TaskRunStatus)),
)
def test_terminal_task_run_states_are_absorbing(
    status: TaskRunStatus,
    target: TaskRunStatus,
) -> None:
    task = TaskRun(
        task_run_id=TaskRunId.parse("TR-1"),
        workflow_run_id=WorkflowRunId.parse("W-1"),
        task_key="fetch",
        created_at=NOW,
        _status=status,
        ended_at=NOW,
        skip_reason=(
            SkipReason.CONDITION_FALSE
            if status is TaskRunStatus.SKIPPED
            else None
        ),
    )

    with pytest.raises(TerminalStateError):
        TaskRunStateMachine().transition(task, target, at=NOW)


@given(
    status=st.sampled_from(
        [
            TaskAttemptStatus.SUCCEEDED,
            TaskAttemptStatus.FAILED,
            TaskAttemptStatus.TIMED_OUT,
            TaskAttemptStatus.CANCELLED,
        ]
    ),
    target=st.sampled_from(list(TaskAttemptStatus)),
)
def test_terminal_attempt_states_are_absorbing(
    status: TaskAttemptStatus,
    target: TaskAttemptStatus,
) -> None:
    attempt = TaskAttempt(
        attempt_id=TaskAttemptId.parse("TA-1"),
        task_run_id=TaskRunId.parse("TR-1"),
        attempt_number=1,
        created_at=NOW,
        _status=status,
        ended_at=NOW,
    )

    with pytest.raises(TerminalStateError):
        TaskAttemptStateMachine().transition(attempt, target, at=NOW)
