"""LOT-13 reference acceptance for V2 executor routing and ThreadExecutor."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.executors as executors
from pyworkflowkit.runtime.contracts import v2_runtime_mvp_contract_snapshot


def test_lot13_qualified_executor_surface_is_explicit() -> None:
    assert "ExecutorRegistry" in executors.__all__
    assert "ThreadExecutor" in executors.__all__

    assert "ExecutorRegistry" not in pyworkflowkit.__all__
    assert "ThreadExecutor" not in pyworkflowkit.__all__


def test_lot13_thread_executor_descriptor_is_frozen() -> None:
    executor = executors.ThreadExecutor(max_workers=1)
    try:
        descriptor = executor.descriptor

        assert descriptor.executor_id == "thread"
        assert descriptor.display_name == "Thread Executor"
        assert descriptor.executor_version == "1"
        assert descriptor.supported_workload_kinds == (
            "python_callable",
            "registered",
        )
        assert descriptor.supports_execution_timeout is True
        assert descriptor.cancellation_capability is executors.CancellationCapability.UNSUPPORTED
        assert descriptor.performs_implicit_workload_retry is False
        assert descriptor.execution_modes == ("worker_thread",)
        assert "deadline_does_not_stop_running_thread" in (descriptor.portability_constraints)
    finally:
        executor.shutdown()


def test_lot13_runtime_contract_declares_registry_routing() -> None:
    snapshot = v2_runtime_mvp_contract_snapshot()

    assert snapshot["contract_version"] == "4"
    assert snapshot["durable_outputs"] is True
    assert snapshot["basic_events"] == "semantic_projection_from_state_transitions"
    assert snapshot["executor_routing"] == "registry"
    assert snapshot["multi_executor_routing"] is True
    assert snapshot["thread_executor"] is True


def test_lot13_registry_order_is_deterministic() -> None:
    thread = executors.ThreadExecutor(max_workers=1)
    try:
        registry = executors.ExecutorRegistry((thread, executors.InlineExecutor()))

        assert registry.executor_ids == ("inline", "thread")
        assert tuple(item.executor_id for item in registry.descriptors()) == (
            "inline",
            "thread",
        )
    finally:
        thread.shutdown()
