"""LOT-04 reference acceptance for canonical V2 runtime state."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.runtime as runtime
import pyworkflowkit.states as states
from pyworkflowkit.domain.runtime import TaskAttempt as LegacyTaskAttempt
from pyworkflowkit.domain.runtime import TaskRun as LegacyTaskRun
from pyworkflowkit.domain.runtime import WorkflowRun as LegacyWorkflowRun
from pyworkflowkit.runtime import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.states.contracts import (
    V2_STATE_PUBLIC_SURFACE,
    V2_TASK_ATTEMPT_STATUSES,
    V2_TASK_RUN_STATUSES,
    V2_WORKFLOW_RUN_STATUSES,
    v2_state_contract_snapshot,
)


def test_qualified_state_surface_matches_lot04_contract() -> None:
    assert tuple(states.__all__) == V2_STATE_PUBLIC_SURFACE

    snapshot = v2_state_contract_snapshot()
    assert snapshot["contract_version"] == "1"
    assert snapshot["workflow_run_statuses"] == list(V2_WORKFLOW_RUN_STATUSES)
    assert snapshot["task_run_statuses"] == list(V2_TASK_RUN_STATUSES)
    assert snapshot["task_attempt_statuses"] == list(V2_TASK_ATTEMPT_STATUSES)


def test_runtime_namespace_now_owns_v2_run_entities() -> None:
    assert TaskAttempt is not LegacyTaskAttempt
    assert TaskRun is not LegacyTaskRun
    assert WorkflowRun is not LegacyWorkflowRun

    assert runtime.TaskAttempt is TaskAttempt
    assert runtime.TaskRun is TaskRun
    assert runtime.WorkflowRun is WorkflowRun


def test_frozen_1_1_root_remains_unchanged() -> None:
    assert "WorkflowRun" not in pyworkflowkit.__all__
    assert "TaskRun" not in pyworkflowkit.__all__
    assert "TaskAttempt" not in pyworkflowkit.__all__


def test_uncertainty_and_cancellation_states_are_public() -> None:
    assert "UNKNOWN_OUTCOME" in V2_WORKFLOW_RUN_STATUSES
    assert "UNKNOWN_OUTCOME" in V2_TASK_RUN_STATUSES
    assert "CANCELLATION_REQUESTED" in V2_TASK_ATTEMPT_STATUSES
    assert "CANCELLATION_UNCONFIRMED" in V2_TASK_ATTEMPT_STATUSES
    assert "REQUIRES_RECONCILIATION" in V2_TASK_ATTEMPT_STATUSES


def test_blocked_is_task_run_state_not_attempt_state() -> None:
    assert "BLOCKED" in V2_TASK_RUN_STATUSES
    assert "BLOCKED" not in V2_TASK_ATTEMPT_STATUSES
