"""LOT-06 reference acceptance for the first end-to-end V2 runtime."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.executors as executors
import pyworkflowkit.runtime as runtime
from pyworkflowkit.application.runtime import WorkflowRuntime as LegacyWorkflowRuntime
from pyworkflowkit.executors import (
    V2_EXECUTOR_CONTRACT_VERSION,
    V2_EXECUTOR_PROTOCOL_METHODS,
    Executor,
    InlineExecutor,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
    v2_executor_contract_snapshot,
)
from pyworkflowkit.runtime import TaskOutcome, WorkflowResult, WorkflowRuntime
from pyworkflowkit.runtime.contracts import (
    V2_RUNTIME_MVP_CONTRACT_VERSION,
    V2_RUNTIME_MVP_RUN_INPUTS,
    V2_RUNTIME_MVP_SURFACE,
    v2_runtime_mvp_contract_snapshot,
)


def test_executor_contract_snapshot_is_machine_readable() -> None:
    snapshot = v2_executor_contract_snapshot()

    assert snapshot["contract_version"] == V2_EXECUTOR_CONTRACT_VERSION
    assert snapshot["protocol_members"] == list(V2_EXECUTOR_PROTOCOL_METHODS)
    assert tuple(executors.__all__) == (
        "AsyncExecutor",
        "CancellationCapability",
        "CancellationStatus",
        "CancellableExecutor",
        "Executor",
        "ExecutorDescriptor",
        "ExecutorRegistry",
        "InlineExecutor",
        "ProcessExecutor",
        "SubprocessCommand",
        "SubprocessExecutor",
        "SubprocessResult",
        "SubprocessSecurityPolicy",
        "TaskCancellationRequest",
        "TaskCancellationResult",
        "TaskExecutionContext",
        "TaskExecutionRequest",
        "TaskExecutionResult",
        "ThreadExecutor",
        "V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS",
        "V2_EXECUTOR_CONTRACT_VERSION",
        "V2_EXECUTOR_PROTOCOL_METHODS",
        "v2_executor_contract_snapshot",
    )


def test_runtime_mvp_contract_snapshot_records_deferred_semantics() -> None:
    snapshot = v2_runtime_mvp_contract_snapshot()

    assert snapshot["contract_version"] == V2_RUNTIME_MVP_CONTRACT_VERSION
    assert snapshot["surface"] == list(V2_RUNTIME_MVP_SURFACE)
    assert snapshot["run_inputs"] == list(V2_RUNTIME_MVP_RUN_INPUTS)
    assert snapshot["retry_execution"] is True
    assert snapshot["timeout_execution"] is True
    assert snapshot["cancellation_commands"] is True
    assert snapshot["durable_outputs"] is True
    assert snapshot["basic_events"] == "semantic_projection_from_state_transitions"


def test_qualified_runtime_now_owns_v2_runtime_facade_and_result() -> None:
    assert WorkflowRuntime is not LegacyWorkflowRuntime
    assert runtime.WorkflowRuntime is WorkflowRuntime
    assert runtime.WorkflowResult is WorkflowResult
    assert runtime.TaskOutcome is TaskOutcome


def test_inline_executor_is_the_v2_local_baseline() -> None:
    assert isinstance(InlineExecutor(), Executor)
    assert TaskExecutionContext is not None
    assert TaskExecutionRequest is not None
    assert TaskExecutionResult is not None


def test_frozen_1_1_root_remains_unchanged() -> None:
    assert pyworkflowkit.WorkflowRuntime is LegacyWorkflowRuntime
    assert "WorkflowResult" not in pyworkflowkit.__all__
    assert "InlineExecutor" not in pyworkflowkit.__all__
