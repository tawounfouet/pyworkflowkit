"""Tests for the runtime state-transition authority."""

from datetime import UTC, datetime
from operator import setitem

import pytest

from pyworkflowkit.application.state_machine import RunStateMachine
from pyworkflowkit.domain.enums import (
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import (
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.errors import InvalidStateTransitionError, TerminalStateError

NOW = datetime(2026, 9, 25, 0, 30, tzinfo=UTC)
LATER = datetime(2026, 9, 25, 0, 31, tzinfo=UTC)


def make_workflow_run(status: WorkflowRunStatus) -> WorkflowRun:
    kwargs: dict[str, object] = {}
    if status is WorkflowRunStatus.RUNNING:
        kwargs["started_at"] = NOW
    elif status in {
        WorkflowRunStatus.SUCCEEDED,
        WorkflowRunStatus.FAILED,
        WorkflowRunStatus.CANCELLED,
    }:
        kwargs["started_at"] = NOW
        kwargs["finished_at"] = LATER

    return WorkflowRun(
        run_id=WorkflowRunId("run-1"),
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
        status=status,
        **kwargs,  # type: ignore[arg-type]
    )


def make_task_run(status: TaskRunStatus) -> TaskRun:
    kwargs: dict[str, object] = {}
    if status is TaskRunStatus.RUNNING:
        kwargs["started_at"] = NOW
    elif status in {
        TaskRunStatus.SUCCEEDED,
        TaskRunStatus.FAILED,
        TaskRunStatus.CANCELLED,
    }:
        kwargs["started_at"] = NOW
        kwargs["finished_at"] = LATER
    elif status is TaskRunStatus.SKIPPED:
        kwargs["finished_at"] = LATER
        kwargs["skip_reason"] = SkipReason.CONDITION_FALSE

    return TaskRun(
        task_run_id=TaskRunId("task-run-1"),
        run_id=WorkflowRunId("run-1"),
        task_id=TaskId("task"),
        status=status,
        **kwargs,  # type: ignore[arg-type]
    )


def make_attempt(status: TaskAttemptStatus) -> TaskAttempt:
    kwargs: dict[str, object] = {}
    if status is not TaskAttemptStatus.RUNNING:
        kwargs["finished_at"] = LATER

    return TaskAttempt(
        attempt_id=TaskAttemptId("attempt-1"),
        task_run_id=TaskRunId("task-run-1"),
        attempt_number=1,
        status=status,
        started_at=NOW,
        **kwargs,  # type: ignore[arg-type]
    )


def test_workflow_pending_can_start() -> None:
    run = make_workflow_run(WorkflowRunStatus.PENDING)

    RunStateMachine().start_workflow(run, at=NOW)

    assert run.status is WorkflowRunStatus.RUNNING
    assert run.started_at == NOW
    assert run.finished_at is None


@pytest.mark.parametrize(
    ("method_name", "expected_status"),
    [
        ("succeed_workflow", WorkflowRunStatus.SUCCEEDED),
        ("fail_workflow", WorkflowRunStatus.FAILED),
        ("cancel_workflow", WorkflowRunStatus.CANCELLED),
    ],
)
def test_running_workflow_can_finish(
    method_name: str,
    expected_status: WorkflowRunStatus,
) -> None:
    run = make_workflow_run(WorkflowRunStatus.RUNNING)
    machine = RunStateMachine()

    getattr(machine, method_name)(run, at=LATER)

    assert run.status is expected_status
    assert run.started_at == NOW
    assert run.finished_at == LATER


@pytest.mark.parametrize(
    "method_name",
    ["succeed_workflow", "fail_workflow", "cancel_workflow"],
)
def test_pending_workflow_cannot_finish_directly(method_name: str) -> None:
    run = make_workflow_run(WorkflowRunStatus.PENDING)
    machine = RunStateMachine()

    with pytest.raises(InvalidStateTransitionError) as exc_info:
        getattr(machine, method_name)(run, at=NOW)

    assert not isinstance(exc_info.value, TerminalStateError)
    assert exc_info.value.entity_type == "WorkflowRun"
    assert exc_info.value.current_status == "PENDING"


def test_running_workflow_cannot_start_again() -> None:
    run = make_workflow_run(WorkflowRunStatus.RUNNING)

    with pytest.raises(InvalidStateTransitionError):
        RunStateMachine().start_workflow(run, at=LATER)


@pytest.mark.parametrize(
    "status",
    [
        WorkflowRunStatus.SUCCEEDED,
        WorkflowRunStatus.FAILED,
        WorkflowRunStatus.CANCELLED,
    ],
)
@pytest.mark.parametrize(
    "method_name",
    [
        "start_workflow",
        "succeed_workflow",
        "fail_workflow",
        "cancel_workflow",
    ],
)
def test_terminal_workflow_rejects_every_transition(
    status: WorkflowRunStatus,
    method_name: str,
) -> None:
    run = make_workflow_run(status)
    machine = RunStateMachine()

    with pytest.raises(TerminalStateError) as exc_info:
        getattr(machine, method_name)(run, at=LATER)

    assert exc_info.value.entity_id == "run-1"
    assert exc_info.value.current_status == status.value


def test_workflow_transition_rejects_naive_timestamp() -> None:
    run = make_workflow_run(WorkflowRunStatus.PENDING)

    with pytest.raises(ValueError, match="timezone-aware"):
        RunStateMachine().start_workflow(run, at=datetime(2026, 9, 25))


def test_pending_task_can_become_ready() -> None:
    task_run = make_task_run(TaskRunStatus.PENDING)

    RunStateMachine().mark_task_ready(task_run)

    assert task_run.status is TaskRunStatus.READY
    assert task_run.started_at is None
    assert task_run.finished_at is None


def test_ready_task_can_start() -> None:
    task_run = make_task_run(TaskRunStatus.READY)

    RunStateMachine().start_task(task_run, at=NOW)

    assert task_run.status is TaskRunStatus.RUNNING
    assert task_run.started_at == NOW
    assert task_run.finished_at is None


@pytest.mark.parametrize(
    ("method_name", "expected_status"),
    [
        ("succeed_task", TaskRunStatus.SUCCEEDED),
        ("fail_task", TaskRunStatus.FAILED),
    ],
)
def test_running_task_can_finish(
    method_name: str,
    expected_status: TaskRunStatus,
) -> None:
    task_run = make_task_run(TaskRunStatus.RUNNING)
    machine = RunStateMachine()

    getattr(machine, method_name)(task_run, at=LATER)

    assert task_run.status is expected_status
    assert task_run.started_at == NOW
    assert task_run.finished_at == LATER


@pytest.mark.parametrize("source", [TaskRunStatus.PENDING, TaskRunStatus.READY])
def test_unstarted_task_can_be_skipped(source: TaskRunStatus) -> None:
    task_run = make_task_run(source)

    RunStateMachine().skip_task(
        task_run,
        reason=SkipReason.DEPENDENCY_FAILED,
        at=NOW,
    )

    assert task_run.status is TaskRunStatus.SKIPPED
    assert task_run.skip_reason is SkipReason.DEPENDENCY_FAILED
    assert task_run.finished_at == NOW


@pytest.mark.parametrize(
    "source",
    [TaskRunStatus.PENDING, TaskRunStatus.READY, TaskRunStatus.RUNNING],
)
def test_non_terminal_task_can_be_cancelled(source: TaskRunStatus) -> None:
    task_run = make_task_run(source)

    RunStateMachine().cancel_task(task_run, at=LATER)

    assert task_run.status is TaskRunStatus.CANCELLED
    assert task_run.finished_at == LATER
    assert task_run.skip_reason is None


@pytest.mark.parametrize(
    ("source", "method_name"),
    [
        (TaskRunStatus.PENDING, "start_task"),
        (TaskRunStatus.PENDING, "succeed_task"),
        (TaskRunStatus.PENDING, "fail_task"),
        (TaskRunStatus.READY, "mark_task_ready"),
        (TaskRunStatus.READY, "succeed_task"),
        (TaskRunStatus.READY, "fail_task"),
        (TaskRunStatus.RUNNING, "mark_task_ready"),
        (TaskRunStatus.RUNNING, "start_task"),
    ],
)
def test_non_terminal_task_rejects_illegal_transitions(
    source: TaskRunStatus,
    method_name: str,
) -> None:
    task_run = make_task_run(source)
    machine = RunStateMachine()

    with pytest.raises(InvalidStateTransitionError) as exc_info:
        if method_name == "mark_task_ready":
            machine.mark_task_ready(task_run)
        else:
            getattr(machine, method_name)(task_run, at=LATER)

    assert not isinstance(exc_info.value, TerminalStateError)
    assert exc_info.value.entity_type == "TaskRun"
    assert exc_info.value.current_status == source.value


def test_running_task_cannot_be_skipped() -> None:
    task_run = make_task_run(TaskRunStatus.RUNNING)

    with pytest.raises(InvalidStateTransitionError):
        RunStateMachine().skip_task(
            task_run,
            reason=SkipReason.FAIL_FAST_ABORT,
            at=LATER,
        )


def test_skip_requires_skip_reason_enum() -> None:
    task_run = make_task_run(TaskRunStatus.PENDING)

    with pytest.raises(TypeError, match="SkipReason"):
        RunStateMachine().skip_task(
            task_run,
            reason="DEPENDENCY_FAILED",  # type: ignore[arg-type]
            at=NOW,
        )


@pytest.mark.parametrize(
    "status",
    [
        TaskRunStatus.SUCCEEDED,
        TaskRunStatus.FAILED,
        TaskRunStatus.SKIPPED,
        TaskRunStatus.CANCELLED,
    ],
)
def test_terminal_task_rejects_ready_transition(status: TaskRunStatus) -> None:
    task_run = make_task_run(status)

    with pytest.raises(TerminalStateError):
        RunStateMachine().mark_task_ready(task_run)


@pytest.mark.parametrize(
    "status",
    [
        TaskRunStatus.SUCCEEDED,
        TaskRunStatus.FAILED,
        TaskRunStatus.SKIPPED,
        TaskRunStatus.CANCELLED,
    ],
)
@pytest.mark.parametrize(
    "method_name",
    ["start_task", "succeed_task", "fail_task", "cancel_task"],
)
def test_terminal_task_rejects_timed_transitions(
    status: TaskRunStatus,
    method_name: str,
) -> None:
    task_run = make_task_run(status)
    machine = RunStateMachine()

    with pytest.raises(TerminalStateError):
        getattr(machine, method_name)(task_run, at=LATER)


@pytest.mark.parametrize(
    "status",
    [
        TaskRunStatus.SUCCEEDED,
        TaskRunStatus.FAILED,
        TaskRunStatus.SKIPPED,
        TaskRunStatus.CANCELLED,
    ],
)
def test_terminal_task_rejects_skip_transition(status: TaskRunStatus) -> None:
    task_run = make_task_run(status)

    with pytest.raises(TerminalStateError):
        RunStateMachine().skip_task(
            task_run,
            reason=SkipReason.FAIL_FAST_ABORT,
            at=LATER,
        )


def test_task_transition_rejects_naive_timestamp() -> None:
    task_run = make_task_run(TaskRunStatus.READY)

    with pytest.raises(ValueError, match="timezone-aware"):
        RunStateMachine().start_task(task_run, at=datetime(2026, 9, 25))


def test_running_attempt_can_succeed() -> None:
    attempt = make_attempt(TaskAttemptStatus.RUNNING)
    attempt.error_type = "stale"
    attempt.error_message = "stale"
    attempt.error_category = "stale"
    attempt.error_metadata = {"stale": True}

    RunStateMachine().succeed_attempt(attempt, at=LATER)

    assert attempt.status is TaskAttemptStatus.SUCCEEDED
    assert attempt.finished_at == LATER
    assert attempt.error_type is None
    assert attempt.error_message is None
    assert attempt.error_category is None
    assert attempt.error_metadata == {}


def test_running_attempt_can_fail_with_structured_error_context() -> None:
    attempt = make_attempt(TaskAttemptStatus.RUNNING)
    metadata = {"provider_code": "TEMP"}

    RunStateMachine().fail_attempt(
        attempt,
        at=LATER,
        error_type="TimeoutError",
        error_message="remote call timed out",
        error_category="transient",
        error_metadata=metadata,
    )
    metadata["provider_code"] = "changed"

    assert attempt.status is TaskAttemptStatus.FAILED
    assert attempt.finished_at == LATER
    assert attempt.error_type == "TimeoutError"
    assert attempt.error_message == "remote call timed out"
    assert attempt.error_category == "transient"
    assert attempt.error_metadata["provider_code"] == "TEMP"
    with pytest.raises(TypeError):
        setitem(attempt.error_metadata, "provider_code", "mutated")


def test_running_attempt_can_be_cancelled() -> None:
    attempt = make_attempt(TaskAttemptStatus.RUNNING)

    RunStateMachine().cancel_attempt(attempt, at=LATER)

    assert attempt.status is TaskAttemptStatus.CANCELLED
    assert attempt.finished_at == LATER


@pytest.mark.parametrize(
    "status",
    [
        TaskAttemptStatus.SUCCEEDED,
        TaskAttemptStatus.FAILED,
        TaskAttemptStatus.CANCELLED,
    ],
)
@pytest.mark.parametrize(
    "method_name",
    ["succeed_attempt", "cancel_attempt"],
)
def test_terminal_attempt_rejects_transition(
    status: TaskAttemptStatus,
    method_name: str,
) -> None:
    attempt = make_attempt(status)
    machine = RunStateMachine()

    with pytest.raises(TerminalStateError):
        getattr(machine, method_name)(attempt, at=LATER)


@pytest.mark.parametrize(
    "status",
    [
        TaskAttemptStatus.SUCCEEDED,
        TaskAttemptStatus.FAILED,
        TaskAttemptStatus.CANCELLED,
    ],
)
def test_terminal_attempt_rejects_fail_transition(status: TaskAttemptStatus) -> None:
    attempt = make_attempt(status)

    with pytest.raises(TerminalStateError):
        RunStateMachine().fail_attempt(
            attempt,
            at=LATER,
            error_type="RuntimeError",
            error_message="boom",
        )


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("error_type", {"error_type": "", "error_message": "boom"}),
        ("error_message", {"error_type": "RuntimeError", "error_message": " "}),
        (
            "error_category",
            {
                "error_type": "RuntimeError",
                "error_message": "boom",
                "error_category": "",
            },
        ),
    ],
)
def test_fail_attempt_rejects_blank_error_fields(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    attempt = make_attempt(TaskAttemptStatus.RUNNING)

    with pytest.raises(ValueError, match=field_name):
        RunStateMachine().fail_attempt(
            attempt,
            at=LATER,
            **kwargs,  # type: ignore[arg-type]
        )


def test_attempt_transition_rejects_naive_timestamp() -> None:
    attempt = make_attempt(TaskAttemptStatus.RUNNING)

    with pytest.raises(ValueError, match="timezone-aware"):
        RunStateMachine().succeed_attempt(
            attempt,
            at=datetime(2026, 9, 25),
        )
