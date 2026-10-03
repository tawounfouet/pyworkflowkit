"""LOT-13 unit tests for the canonical V2 ThreadExecutor."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit.authoring import RegisteredWorkload
from pyworkflowkit.diagnostics import FailureCategory, OutcomeUncertainty, Retryability
from pyworkflowkit.errors import ExecutorShutdownError
from pyworkflowkit.executors import (
    CancellationCapability,
    Executor,
    TaskExecutionContext,
    TaskExecutionRequest,
    ThreadExecutor,
)
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)


def _context() -> TaskExecutionContext:
    return TaskExecutionContext(
        workflow_run_id=WorkflowRunId.parse("W-1"),
        task_run_id=TaskRunId.parse("TR-1"),
        attempt_id=TaskAttemptId.parse("TA-1"),
        attempt_number=1,
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-1"),
        ),
    )


def test_thread_executor_satisfies_v2_protocol_and_declares_soft_boundary() -> None:
    executor = ThreadExecutor(max_workers=2)
    try:
        assert isinstance(executor, Executor)
        assert executor.descriptor.executor_id == "thread"
        assert executor.descriptor.supports_execution_timeout is True
        assert executor.descriptor.cancellation_capability is CancellationCapability.UNSUPPORTED
        assert "deadline_does_not_stop_running_thread" in (
            executor.descriptor.portability_constraints
        )
        assert executor.max_workers == 2
    finally:
        executor.shutdown()


def test_thread_executor_invokes_callable_on_worker_thread() -> None:
    caller_name = threading.current_thread().name
    executor = ThreadExecutor(max_workers=1, thread_name_prefix="pwk-lot13")
    try:
        result = executor.execute(
            TaskExecutionRequest(
                task_key="threaded",
                workload=lambda: threading.current_thread().name,
                executor_key="thread",
                context=_context(),
            )
        )
    finally:
        executor.shutdown()

    assert result.succeeded is True
    assert isinstance(result.output, str)
    assert result.output != caller_name
    assert result.output.startswith("pwk-lot13")


def test_thread_executor_registered_workload_receives_parameters() -> None:
    def registered(context: TaskExecutionContext) -> str:
        return context.workload_parameters["mode"]

    executor = ThreadExecutor({"jobs.refresh": registered}, max_workers=1)
    try:
        result = executor.execute(
            TaskExecutionRequest(
                task_key="refresh",
                workload=RegisteredWorkload(
                    "jobs.refresh",
                    parameters=(("mode", "full"),),
                    executor_key="thread",
                ),
                executor_key="thread",
                context=_context(),
            )
        )
    finally:
        executor.shutdown()

    assert result.succeeded is True
    assert result.output == "full"


def test_thread_soft_timeout_is_uncertain_and_never_claims_work_stopped() -> None:
    release = threading.Event()
    finished = threading.Event()

    def slow() -> str:
        try:
            release.wait(timeout=2)
            return "finished"
        finally:
            finished.set()

    executor = ThreadExecutor(max_workers=1)
    try:
        request = TaskExecutionRequest(
            task_key="slow",
            workload=slow,
            executor_key="thread",
            context=_context(),
            deadline_at=datetime.now(tz=UTC) + timedelta(milliseconds=20),
        )

        result = executor.execute(request)

        assert result.succeeded is False
        assert result.failure is not None
        assert result.failure.category is FailureCategory.TIMEOUT
        assert result.failure.retryability is Retryability.RETRYABLE_AFTER_RECONCILIATION
        assert result.failure.uncertainty is OutcomeUncertainty.REQUIRES_RECONCILIATION
        assert "may still be running" in result.failure.message_summary

        release.set()
        assert finished.wait(timeout=1)
    finally:
        release.set()
        executor.shutdown()


def test_thread_executor_propagates_workload_exception_as_failure_evidence() -> None:
    def explode() -> None:
        raise ValueError("boom")

    executor = ThreadExecutor(max_workers=1)
    try:
        result = executor.execute(
            TaskExecutionRequest(
                task_key="explode",
                workload=explode,
                executor_key="thread",
                context=_context(),
            )
        )
    finally:
        executor.shutdown()

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_code == "ValueError"
    assert result.failure.message_summary == "boom"
    assert result.failure.source_component == "thread_executor"


def test_thread_executor_rejects_submissions_after_shutdown() -> None:
    executor = ThreadExecutor(max_workers=1)
    executor.shutdown()

    with pytest.raises(ExecutorShutdownError):
        executor.execute(
            TaskExecutionRequest(
                task_key="late",
                workload=lambda: None,
                executor_key="thread",
                context=_context(),
            )
        )


@pytest.mark.parametrize("max_workers", [0, -1])
def test_thread_executor_rejects_non_positive_worker_count(max_workers: int) -> None:
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        ThreadExecutor(max_workers=max_workers)


def test_thread_executor_rejects_bool_worker_count() -> None:
    with pytest.raises(TypeError, match="integer"):
        ThreadExecutor(max_workers=True)  # type: ignore[arg-type]


def test_thread_executor_deadline_already_elapsed_fails_closed() -> None:
    executor = ThreadExecutor(max_workers=1)
    try:
        result = executor.execute(
            TaskExecutionRequest(
                task_key="expired",
                workload=lambda: time.sleep(0.01),
                executor_key="thread",
                context=_context(),
                deadline_at=datetime.now(tz=UTC) - timedelta(seconds=1),
            )
        )
    finally:
        executor.shutdown()

    assert result.failure is not None
    assert result.failure.category is FailureCategory.TIMEOUT
