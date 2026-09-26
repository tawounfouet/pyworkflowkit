"""Domain enums for workflow and task lifecycle semantics."""

from enum import StrEnum


class WorkflowRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskRunStatus(StrEnum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class TaskAttemptStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SkipReason(StrEnum):
    CONDITION_FALSE = "CONDITION_FALSE"
    DEPENDENCY_FAILED = "DEPENDENCY_FAILED"
    FAIL_FAST_ABORT = "FAIL_FAST_ABORT"
    BRANCH_NOT_SELECTED = "BRANCH_NOT_SELECTED"


class FailurePolicy(StrEnum):
    FAIL_FAST = "FAIL_FAST"


class TimeoutMode(StrEnum):
    NONE = "NONE"
    SOFT = "SOFT"
    HARD = "HARD"


class BackoffStrategy(StrEnum):
    NONE = "NONE"
    FIXED = "FIXED"
    LINEAR = "LINEAR"
    EXPONENTIAL = "EXPONENTIAL"


class RuntimeEventType(StrEnum):
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_SUCCEEDED = "WORKFLOW_SUCCEEDED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    WORKFLOW_CANCELLED = "WORKFLOW_CANCELLED"

    TASK_READY = "TASK_READY"
    TASK_STARTED = "TASK_STARTED"
    TASK_RETRYING = "TASK_RETRYING"
    TASK_SUCCEEDED = "TASK_SUCCEEDED"
    TASK_FAILED = "TASK_FAILED"
    TASK_SKIPPED = "TASK_SKIPPED"


WORKFLOW_TERMINAL_STATUSES = frozenset(
    {
        WorkflowRunStatus.SUCCEEDED,
        WorkflowRunStatus.FAILED,
        WorkflowRunStatus.CANCELLED,
    }
)

TASK_TERMINAL_STATUSES = frozenset(
    {
        TaskRunStatus.SUCCEEDED,
        TaskRunStatus.FAILED,
        TaskRunStatus.SKIPPED,
        TaskRunStatus.CANCELLED,
    }
)

ATTEMPT_TERMINAL_STATUSES = frozenset(
    {
        TaskAttemptStatus.SUCCEEDED,
        TaskAttemptStatus.FAILED,
        TaskAttemptStatus.CANCELLED,
    }
)


__all__ = [
    "ATTEMPT_TERMINAL_STATUSES",
    "TASK_TERMINAL_STATUSES",
    "WORKFLOW_TERMINAL_STATUSES",
    "BackoffStrategy",
    "FailurePolicy",
    "RuntimeEventType",
    "SkipReason",
    "TaskAttemptStatus",
    "TaskRunStatus",
    "TimeoutMode",
    "WorkflowRunStatus",
]
