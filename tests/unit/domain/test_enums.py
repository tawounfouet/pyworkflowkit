"""Tests for lifecycle and policy enums."""

from pyworkflowkit.domain.enums import (
    ATTEMPT_TERMINAL_STATUSES,
    TASK_TERMINAL_STATUSES,
    WORKFLOW_TERMINAL_STATUSES,
    BackoffStrategy,
    FailurePolicy,
    RuntimeEventType,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)


def test_workflow_status_values_are_stable_strings() -> None:
    assert [status.value for status in WorkflowRunStatus] == [
        "PENDING",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ]


def test_task_status_values_are_stable_strings() -> None:
    assert [status.value for status in TaskRunStatus] == [
        "PENDING",
        "READY",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "SKIPPED",
        "CANCELLED",
    ]


def test_attempt_has_no_pending_or_ready_state() -> None:
    assert set(TaskAttemptStatus) == {
        TaskAttemptStatus.RUNNING,
        TaskAttemptStatus.SUCCEEDED,
        TaskAttemptStatus.FAILED,
        TaskAttemptStatus.CANCELLED,
    }


def test_terminal_status_sets_are_explicit() -> None:
    assert {
        WorkflowRunStatus.SUCCEEDED,
        WorkflowRunStatus.FAILED,
        WorkflowRunStatus.CANCELLED,
    } == WORKFLOW_TERMINAL_STATUSES
    assert {
        TaskRunStatus.SUCCEEDED,
        TaskRunStatus.FAILED,
        TaskRunStatus.SKIPPED,
        TaskRunStatus.CANCELLED,
    } == TASK_TERMINAL_STATUSES
    assert {
        TaskAttemptStatus.SUCCEEDED,
        TaskAttemptStatus.FAILED,
        TaskAttemptStatus.CANCELLED,
    } == ATTEMPT_TERMINAL_STATUSES


def test_policy_and_reason_enum_values_are_stable() -> None:
    assert FailurePolicy.FAIL_FAST == "FAIL_FAST"
    assert SkipReason.DEPENDENCY_FAILED == "DEPENDENCY_FAILED"
    assert SkipReason.FAIL_FAST_ABORT == "FAIL_FAST_ABORT"
    assert BackoffStrategy.EXPONENTIAL == "EXPONENTIAL"


def test_runtime_event_type_contains_core_lifecycle_facts() -> None:
    assert RuntimeEventType.WORKFLOW_STARTED == "WORKFLOW_STARTED"
    assert RuntimeEventType.TASK_RETRYING == "TASK_RETRYING"
    assert RuntimeEventType.TASK_FAILED == "TASK_FAILED"
