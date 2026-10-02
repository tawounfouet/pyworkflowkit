"""LOT-08 reference acceptance for timeout and cancellation semantics."""

from pyworkflowkit.executors import (
    V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS,
    CancellationCapability,
    CancellationStatus,
    CancellableExecutor,
    InlineExecutor,
    TaskCancellationRequest,
    TaskCancellationResult,
    TaskExecutionRequest,
    v2_executor_contract_snapshot,
)
from pyworkflowkit.policies import (
    V2_TIMEOUT_CONTRACT_VERSION,
    TimeoutPolicy,
    v2_timeout_contract_snapshot,
)
from pyworkflowkit.runtime import CancellationResult, WorkflowRuntime
from pyworkflowkit.runtime.contracts import v2_runtime_mvp_contract_snapshot


def test_timeout_contract_is_machine_readable() -> None:
    snapshot = v2_timeout_contract_snapshot()

    assert snapshot["contract_version"] == V2_TIMEOUT_CONTRACT_VERSION
    assert snapshot["policy_fields"] == ["execution_timeout"]
    assert snapshot["timeout_means"] == "local_deadline_exceeded"
    assert snapshot["confirmed_external_stop_required_for_terminal_timeout"] is True


def test_executor_cancellation_contract_is_machine_readable() -> None:
    snapshot = v2_executor_contract_snapshot()

    assert snapshot["cancellable_protocol_members"] == list(
        V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS
    )
    assert snapshot["cancellation_statuses"] == [value.value for value in CancellationStatus]
    assert snapshot["cancellation_capabilities"] == [
        value.value for value in CancellationCapability
    ]


def test_inline_executor_does_not_fake_timeout_or_cancellation() -> None:
    descriptor = InlineExecutor().descriptor

    assert descriptor.supports_execution_timeout is False
    assert descriptor.cancellation_capability is CancellationCapability.UNSUPPORTED
    assert not isinstance(InlineExecutor(), CancellableExecutor)


def test_timeout_and_cancellation_public_types_exist() -> None:
    assert TimeoutPolicy is not None
    assert TaskExecutionRequest is not None
    assert TaskCancellationRequest is not None
    assert TaskCancellationResult is not None
    assert CancellationResult is not None
    assert WorkflowRuntime is not None


def test_runtime_contract_marks_lot08_active() -> None:
    snapshot = v2_runtime_mvp_contract_snapshot()

    assert snapshot["timeout_execution"] is True
    assert snapshot["cancellation_commands"] is True
