"""LOT-14 unit tests for the canonical V2 AsyncExecutor."""

from __future__ import annotations

import asyncio
import threading
import time
from datetime import UTC, datetime, timedelta

from pyworkflowkit.diagnostics import FailureCategory, OutcomeUncertainty
from pyworkflowkit.executors import (
    AsyncExecutor,
    CancellationStatus,
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


def _context(attempt_id: str = "TA-async") -> TaskExecutionContext:
    return TaskExecutionContext(
        workflow_run_id=WorkflowRunId.parse("W-async"),
        task_run_id=TaskRunId.parse("TR-async"),
        attempt_id=TaskAttemptId.parse(attempt_id),
        attempt_number=1,
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-async"),
        ),
    )


def _request(
    workload: object,
    *,
    attempt_id: str = "TA-async",
    deadline_at: datetime | None = None,
) -> TaskExecutionRequest:
    return TaskExecutionRequest(
        task_key="async-task",
        workload=workload,  # type: ignore[arg-type]
        executor_key="async",
        context=_context(attempt_id),
        deadline_at=deadline_at,
    )


def test_async_executor_awaits_handler_on_dedicated_loop() -> None:
    async def handler() -> str:
        await asyncio.sleep(0)
        return threading.current_thread().name

    executor = AsyncExecutor(max_concurrency=2, loop_thread_name="pwk-lot14-async")
    try:
        result = executor.execute(_request(handler))
    finally:
        executor.shutdown()

    assert result.succeeded is True
    assert isinstance(result.output, str)
    assert result.output == "pwk-lot14-async"


def test_async_executor_native_execute_async_does_not_block_caller_loop() -> None:
    async def handler() -> str:
        await asyncio.sleep(0.01)
        return "ok"

    executor = AsyncExecutor(max_concurrency=1)
    try:
        result = asyncio.run(executor.execute_async(_request(handler)))
    finally:
        executor.shutdown()

    assert result.succeeded is True
    assert result.output == "ok"


def test_async_executor_rejects_nonawaitable_handler_result() -> None:
    executor = AsyncExecutor(max_concurrency=1)
    try:
        result = executor.execute(_request(lambda: "sync"))
    finally:
        executor.shutdown()

    assert result.failure is not None
    assert result.failure.category is FailureCategory.CONTRACT_VIOLATION
    assert result.failure.error_code == "PWK-ASYNC-NON-AWAITABLE"


def test_async_executor_soft_timeout_is_uncertain() -> None:
    async def slow() -> None:
        await asyncio.sleep(5)

    executor = AsyncExecutor(max_concurrency=1)
    try:
        result = executor.execute(
            _request(
                slow,
                deadline_at=datetime.now(tz=UTC) + timedelta(milliseconds=30),
            )
        )
        time.sleep(0.05)
    finally:
        executor.shutdown(wait=False)

    assert result.failure is not None
    assert result.failure.category is FailureCategory.TIMEOUT
    assert result.failure.uncertainty is OutcomeUncertainty.REQUIRES_RECONCILIATION
    assert result.failure.error_code == "PWK-ASYNC-SOFT-TIMEOUT"


def test_async_executor_cancellation_is_requested_not_falsely_confirmed() -> None:
    async def slow() -> None:
        await asyncio.sleep(5)

    request = _request(slow, attempt_id="TA-cancel-async")
    executor = AsyncExecutor(max_concurrency=1)
    holder: list[object] = []
    worker = threading.Thread(
        target=lambda: holder.append(executor.execute(request)),
        daemon=True,
    )
    worker.start()
    time.sleep(0.05)

    cancellation = executor.cancel(
        TaskCancellationRequest(
            workflow_run_id=request.context.workflow_run_id,
            task_run_id=request.context.task_run_id,
            attempt_id=request.context.attempt_id,
            task_key=request.task_key,
            requested_at=datetime.now(tz=UTC),
        )
    )
    worker.join(timeout=2)
    executor.shutdown(wait=False)

    assert cancellation.status is CancellationStatus.REQUESTED
    assert not worker.is_alive()
    assert holder
    result = holder[0]
    assert result.failure is not None  # type: ignore[union-attr]
    assert result.failure.category is FailureCategory.CANCELLED  # type: ignore[union-attr]
