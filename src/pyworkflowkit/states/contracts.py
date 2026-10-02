"""Machine-readable LOT-04 V2 state-machine API contract."""

from __future__ import annotations

V2_STATE_API_CONTRACT_VERSION = "1"

V2_STATE_PUBLIC_SURFACE: tuple[str, ...] = (
    "BlockReason",
    "SkipReason",
    "TaskAttemptStateMachine",
    "TaskAttemptStatus",
    "TaskRunStateMachine",
    "TaskRunStatus",
    "WorkflowRunStateMachine",
    "WorkflowRunStatus",
)

V2_WORKFLOW_RUN_STATUSES: tuple[str, ...] = (
    "PENDING",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLATION_REQUESTED",
    "CANCELLED",
    "TIMED_OUT",
    "UNKNOWN_OUTCOME",
)

V2_TASK_RUN_STATUSES: tuple[str, ...] = (
    "PENDING",
    "READY",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "SKIPPED",
    "CANCELLED",
    "TIMED_OUT",
    "BLOCKED",
    "UNKNOWN_OUTCOME",
)

V2_TASK_ATTEMPT_STATUSES: tuple[str, ...] = (
    "PENDING",
    "STARTING",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "TIMED_OUT",
    "CANCELLATION_REQUESTED",
    "CANCELLED",
    "CANCELLATION_UNCONFIRMED",
    "UNKNOWN_OUTCOME",
    "REQUIRES_RECONCILIATION",
)


def v2_state_contract_snapshot() -> dict[str, object]:
    return {
        "contract_version": V2_STATE_API_CONTRACT_VERSION,
        "surface": list(V2_STATE_PUBLIC_SURFACE),
        "workflow_run_statuses": list(V2_WORKFLOW_RUN_STATUSES),
        "task_run_statuses": list(V2_TASK_RUN_STATUSES),
        "task_attempt_statuses": list(V2_TASK_ATTEMPT_STATUSES),
    }


__all__ = [
    "V2_STATE_API_CONTRACT_VERSION",
    "V2_STATE_PUBLIC_SURFACE",
    "V2_TASK_ATTEMPT_STATUSES",
    "V2_TASK_RUN_STATUSES",
    "V2_WORKFLOW_RUN_STATUSES",
    "v2_state_contract_snapshot",
]
