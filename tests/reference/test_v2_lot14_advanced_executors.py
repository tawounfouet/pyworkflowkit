"""LOT-14 reference acceptance for advanced canonical V2 executors."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.executors as executors


def test_lot14_qualified_executor_surface_is_explicit() -> None:
    expected = {
        "AsyncExecutor",
        "ProcessExecutor",
        "SubprocessCommand",
        "SubprocessExecutor",
        "SubprocessResult",
        "SubprocessSecurityPolicy",
    }
    assert expected.issubset(set(executors.__all__))

    for name in expected:
        assert name not in pyworkflowkit.__all__


def test_lot14_executor_descriptors_publish_distinct_physical_semantics() -> None:
    process = executors.ProcessExecutor(max_workers=1)
    async_executor = executors.AsyncExecutor(max_concurrency=1)
    subprocess_executor = executors.SubprocessExecutor(max_workers=1)
    try:
        assert process.descriptor.executor_id == "process"
        assert process.descriptor.execution_modes == ("child_process",)
        assert process.descriptor.supports_execution_timeout is True
        assert (
            process.descriptor.cancellation_capability is executors.CancellationCapability.CONFIRMED
        )
        assert "handler_must_be_picklable" in process.descriptor.portability_constraints

        assert async_executor.descriptor.executor_id == "async"
        assert async_executor.descriptor.execution_modes == (
            "asyncio",
            "synchronous_bridge",
        )
        assert (
            async_executor.descriptor.cancellation_capability
            is executors.CancellationCapability.BEST_EFFORT
        )
        assert "cancellation_is_cooperative" in (async_executor.descriptor.portability_constraints)

        assert subprocess_executor.descriptor.executor_id == "subprocess"
        assert subprocess_executor.descriptor.execution_modes == ("external_process",)
        assert (
            subprocess_executor.descriptor.cancellation_capability
            is executors.CancellationCapability.CONFIRMED
        )
        assert "shell_disabled" in subprocess_executor.descriptor.portability_constraints
        assert "subprocess" in subprocess_executor.descriptor.supported_workload_kinds
    finally:
        process.shutdown(wait=False)
        async_executor.shutdown(wait=False)
        subprocess_executor.shutdown(wait=False)


def test_lot14_executor_contract_snapshot_records_fail_closed_boundaries() -> None:
    snapshot = executors.v2_executor_contract_snapshot()

    assert snapshot["contract_version"] == "4"
    assert snapshot["executor_registry"] is True
    assert snapshot["thread_executor"] is True
    assert snapshot["process_executor"] is True
    assert snapshot["async_executor"] is True
    assert snapshot["subprocess_executor"] is True
    assert snapshot["process_serialization_boundary"] == "pickle_fail_closed"
    assert snapshot["async_cancellation"] == "cooperative_requested"
    assert snapshot["subprocess_shell"] is False


def test_lot14_subprocess_command_is_portable_and_shell_free_by_contract() -> None:
    command = executors.SubprocessCommand(
        argv=("python", "-c", "print('hello')"),
    )

    assert command.executor_key == "subprocess"
    assert command.workload_kind == "subprocess"
    assert command.portability.value == "portable"
    assert command.fingerprint_payload()["argv"] == [
        "python",
        "-c",
        "print('hello')",
    ]
