"""LOT-14 unit tests for the canonical V2 ProcessExecutor."""

from __future__ import annotations

import os
import threading
import time
from datetime import UTC, datetime, timedelta

from pyworkflowkit.diagnostics import FailureCategory, OutcomeUncertainty
from pyworkflowkit.executors import (
    CancellationStatus,
    ProcessExecutor,
    TaskCancellationRequest,
    TaskExecutionContext,
    TaskExecutionRequest,
)
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)


def _context(attempt_id: str = "TA-process") -> TaskExecutionContext:
    return TaskExecutionContext(
        workflow_run_id=WorkflowRunId.parse("W-process"),
        task_run_id=TaskRunId.parse("TR-process"),
        attempt_id=TaskAttemptId.parse(attempt_id),
        attempt_number=1,
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-process"),
        ),
    )


def _sleep_short() -> None:
    time.sleep(0.5)


def _sleep_long() -> None:
    time.sleep(2.0)


def _return_unserializable() -> object:
    return open(__file__)


def _raise_worker_error() -> None:
    raise RuntimeError("worker-boom")


def _request(
    workload: object,
    *,
    attempt_id: str = "TA-process",
    deadline_at: datetime | None = None,
) -> TaskExecutionRequest:
    return TaskExecutionRequest(
        task_key="process-task",
        workload=workload,  # type: ignore[arg-type]
        executor_key="process",
        context=_context(attempt_id),
        deadline_at=deadline_at,
    )


def test_process_executor_runs_in_an_isolated_process() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        result = executor.execute(_request(os.getpid))
    finally:
        executor.shutdown()

    assert result.succeeded is True
    assert isinstance(result.output, int)
    assert result.output != os.getpid()


def test_process_executor_rejects_unpicklable_handler_before_spawn() -> None:
    executor = ProcessExecutor(max_workers=1)
    try:
        result = executor.execute(_request(lambda: "not-portable"))
    finally:
        executor.shutdown()

    assert result.failure is not None
    assert result.failure.category is FailureCategory.CONTRACT_VIOLATION
    assert result.failure.error_code == "PWK-PROCESS-SERIALIZATION"


def test_process_executor_reports_nonportable_result_without_transport_crash() -> None:
    handler = _return_unserializable
    executor = ProcessExecutor(max_workers=1)
    try:
        result = executor.execute(_request(handler))
    finally:
        executor.shutdown()

    assert result.failure is not None
    assert result.failure.error_code == "PWK-PROCESS-RESULT-NONPORTABLE"
    assert result.failure.category is FailureCategory.CONTRACT_VIOLATION


def test_process_executor_hard_timeout_is_known() -> None:
    handler = _sleep_short
    executor = ProcessExecutor(max_workers=1)
    try:
        result = executor.execute(
            _request(
                handler,
                deadline_at=datetime.now(tz=UTC) + timedelta(milliseconds=30),
            )
        )
    finally:
        executor.shutdown(wait=False)

    assert result.failure is not None
    assert result.failure.category is FailureCategory.TIMEOUT
    assert result.failure.uncertainty is OutcomeUncertainty.KNOWN
    assert result.failure.error_code == "PWK-PROCESS-HARD-TIMEOUT"


def test_process_executor_hard_cancellation_is_confirmed() -> None:
    request = _request(
        _sleep_long,
        attempt_id="TA-cancel-process",
    )
    executor = ProcessExecutor(max_workers=1)
    holder: list[object] = []

    worker = threading.Thread(
        target=lambda: holder.append(executor.execute(request)),
        daemon=True,
    )
    worker.start()
    time.sleep(0.15)

    cancellation = executor.cancel(
        TaskCancellationRequest(
            workflow_run_id=request.context.workflow_run_id,
            task_run_id=request.context.task_run_id,
            attempt_id=request.context.attempt_id,
            task_key=request.task_key,
            requested_at=datetime.now(tz=UTC),
        )
    )
    worker.join(timeout=3)
    executor.shutdown(wait=False)

    assert cancellation.status is CancellationStatus.CONFIRMED
    assert not worker.is_alive()
    assert holder
    result = holder[0]
    assert hasattr(result, "failure")
    assert result.failure is not None  # type: ignore[union-attr]
    assert result.failure.category is FailureCategory.CANCELLED  # type: ignore[union-attr]
