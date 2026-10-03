"""Canonical V2 asyncio executor with cooperative cancellation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from inspect import isawaitable
from threading import Event, RLock, Thread
from typing import cast

from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.errors import ExecutorShutdownError
from pyworkflowkit.executors._common import (
    PythonHandler,
    bound_context,
    failure_result,
    resolve_handler,
    resolve_invocation_arity,
)
from pyworkflowkit.executors.contracts import (
    CancellableExecutor,
    CancellationCapability,
    CancellationStatus,
    Executor,
    ExecutorDescriptor,
    TaskCancellationRequest,
    TaskCancellationResult,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from pyworkflowkit.runtime.identity import TaskAttemptId

_ASYNC_EXECUTOR_ID = "async"


@dataclass(slots=True)
class _AsyncExecution:
    request: TaskExecutionRequest
    handler: PythonHandler
    arity: int
    context: TaskExecutionContext
    done_event: Event = field(default_factory=Event)
    task: asyncio.Task[TaskExecutionResult] | None = None
    result: TaskExecutionResult | None = None
    cancellation_requested: bool = False
    detached: bool = False


class AsyncExecutor:
    """Execute awaitable trusted-Python workloads on a dedicated asyncio event loop."""

    def __init__(
        self,
        bindings: Mapping[str, PythonHandler] | None = None,
        *,
        max_concurrency: int = 100,
        loop_thread_name: str = "pyworkflowkit-v2-async",
    ) -> None:
        if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int):
            raise TypeError("max_concurrency must be an integer")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be greater than or equal to 1")
        if not isinstance(loop_thread_name, str) or not loop_thread_name.strip():
            raise ValueError("loop_thread_name must not be blank")

        self._bindings: dict[str, PythonHandler] = {}
        for key, handler in (bindings or {}).items():
            self.register(key, handler)

        self._max_concurrency = max_concurrency
        self._loop = asyncio.new_event_loop()
        self._loop_started = Event()
        self._loop_stopped = Event()
        self._loop_thread = Thread(
            target=self._run_loop,
            name=loop_thread_name,
            daemon=True,
        )
        self._active: dict[TaskAttemptId, _AsyncExecution] = {}
        self._completed: set[TaskAttemptId] = set()
        self._shutdown = False
        self._lock = RLock()
        self._descriptor = ExecutorDescriptor(
            executor_id=_ASYNC_EXECUTOR_ID,
            display_name="Async Executor",
            executor_version="1",
            capabilities=(
                "cooperative_cancellation",
                "dedicated_event_loop",
                "native_async",
                "trusted_python",
            ),
            execution_modes=("asyncio", "synchronous_bridge"),
            portability_constraints=(
                "cancellation_is_cooperative",
                "same_process",
                "shared_memory",
            ),
            supported_workload_kinds=("python_callable", "registered"),
            performs_implicit_workload_retry=False,
            supports_execution_timeout=True,
            cancellation_capability=CancellationCapability.BEST_EFFORT,
        )
        self._loop_thread.start()
        self._loop_started.wait()

    @property
    def descriptor(self) -> ExecutorDescriptor:
        return self._descriptor

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    @property
    def is_shutdown(self) -> bool:
        with self._lock:
            return self._shutdown

    def register(self, key: str, handler: PythonHandler) -> None:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("registered workload key must not be empty")
        if not callable(handler):
            raise TypeError("registered workload handler must be callable")
        if key in self._bindings:
            raise ValueError(f"registered workload {key!r} already exists")
        self._bindings[key] = handler

    def execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        prepared = self._prepare(request)
        if isinstance(prepared, TaskExecutionResult):
            return prepared

        remaining = _remaining_seconds(request)
        if remaining is not None and remaining <= 0:
            return _known_timeout(request)

        execution = prepared
        attempt_id = request.context.attempt_id
        with self._lock:
            if self._shutdown:
                raise ExecutorShutdownError(executor_key=self.descriptor.executor_id)
            if len(self._active) >= self._max_concurrency:
                return failure_result(
                    request,
                    error_code="PWK-ASYNC-CAPACITY",
                    category=FailureCategory.RESOURCE_EXHAUSTED,
                    retryability=Retryability.RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    source_component="async_executor",
                    summary="async executor capacity is saturated",
                )
            self._active[attempt_id] = execution
            self._loop.call_soon_threadsafe(self._start_execution, attempt_id)

        completed = execution.done_event.wait(timeout=remaining)
        if not completed:
            with self._lock:
                current = self._active.get(attempt_id)
                if current is not None:
                    current.detached = True
                    current.cancellation_requested = True
                    task = current.task
                    if task is not None:
                        self._loop.call_soon_threadsafe(task.cancel)
            return _soft_timeout(request)

        with self._lock:
            current = self._active.pop(attempt_id, execution)
            self._completed.add(attempt_id)
            result = current.result
        if result is None:
            return failure_result(
                request,
                error_code="PWK-ASYNC-MISSING-RESULT",
                category=FailureCategory.INTERNAL,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="async_executor",
                summary="async execution completed without a result",
            )
        return result

    async def execute_async(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        """Await the same canonical execution contract without blocking the caller loop."""

        return await asyncio.to_thread(self.execute, request)

    def cancel(self, request: TaskCancellationRequest) -> TaskCancellationResult:
        if not isinstance(request, TaskCancellationRequest):
            raise TypeError("request must be a TaskCancellationRequest")

        with self._lock:
            execution = self._active.get(request.attempt_id)
            if execution is None:
                status = (
                    CancellationStatus.ALREADY_TERMINAL
                    if request.attempt_id in self._completed
                    else CancellationStatus.UNCONFIRMED
                )
                reason = (
                    "async_execution_already_terminal"
                    if status is CancellationStatus.ALREADY_TERMINAL
                    else "async_execution_handle_not_available"
                )
                return TaskCancellationResult(
                    status=status,
                    attempt_id=request.attempt_id,
                    reason=reason,
                )
            if execution.done_event.is_set():
                return TaskCancellationResult(
                    status=CancellationStatus.ALREADY_TERMINAL,
                    attempt_id=request.attempt_id,
                    reason="async_execution_already_terminal",
                )

            execution.cancellation_requested = True
            task = execution.task
            if task is not None:
                self._loop.call_soon_threadsafe(task.cancel)

        return TaskCancellationResult(
            status=CancellationStatus.REQUESTED,
            attempt_id=request.attempt_id,
            reason="asyncio_task_cancellation_requested",
        )

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            executions = tuple(self._active.values())

        if wait:
            for execution in executions:
                execution.done_event.wait()
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._loop_thread.join()
            return

        for execution in executions:
            with self._lock:
                execution.cancellation_requested = True
                task = execution.task
            if task is not None:
                self._loop.call_soon_threadsafe(task.cancel)
        self._loop.call_soon_threadsafe(self._loop.stop)

    def __enter__(self) -> AsyncExecutor:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.shutdown(wait=True)

    def _prepare(
        self,
        request: TaskExecutionRequest,
    ) -> _AsyncExecution | TaskExecutionResult:
        if not isinstance(request, TaskExecutionRequest):
            raise TypeError("request must be a TaskExecutionRequest")
        if request.executor_key != self.descriptor.executor_id:
            return failure_result(
                request,
                error_code="PWK-EXECUTOR-MISMATCH",
                category=FailureCategory.CAPABILITY,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="async_executor",
                summary=(
                    f"request requires executor {request.executor_key!r}, "
                    f"but AsyncExecutor is {self.descriptor.executor_id!r}"
                ),
            )

        handler, parameters = resolve_handler(request, self._bindings)
        if handler is None:
            return failure_result(
                request,
                error_code="PWK-ASYNC-WORKLOAD-UNRESOLVED",
                category=FailureCategory.CAPABILITY,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="async_executor",
                summary="AsyncExecutor cannot resolve the declared workload",
            )
        try:
            arity = resolve_invocation_arity(handler)
        except (TypeError, ValueError) as exc:
            return failure_result(
                request,
                error_code="PWK-ASYNC-HANDLER-CONTRACT",
                category=FailureCategory.CONTRACT_VIOLATION,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="async_executor",
                summary=str(exc),
            )

        return _AsyncExecution(
            request=request,
            handler=handler,
            arity=arity,
            context=bound_context(request, parameters),
        )

    def _start_execution(self, attempt_id: TaskAttemptId) -> None:
        with self._lock:
            execution = self._active.get(attempt_id)
            if execution is None:
                return
            task = self._loop.create_task(self._invoke_async(execution))
            execution.task = task
            cancel_now = execution.cancellation_requested

        task.add_done_callback(partial(self._complete_execution, attempt_id))
        if cancel_now:
            task.cancel()

    async def _invoke_async(self, execution: _AsyncExecution) -> TaskExecutionResult:
        request = execution.request
        try:
            raw_awaitable = (
                execution.handler()
                if execution.arity == 0
                else execution.handler(execution.context)
            )
        except Exception as exc:
            return failure_result(
                request,
                error_code=type(exc).__name__,
                category=FailureCategory.INTERNAL,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="async_executor",
                summary=str(exc) or type(exc).__name__,
            )

        if not isawaitable(raw_awaitable):
            return failure_result(
                request,
                error_code="PWK-ASYNC-NON-AWAITABLE",
                category=FailureCategory.CONTRACT_VIOLATION,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="async_executor",
                summary="AsyncExecutor handler must return an awaitable",
            )

        try:
            raw = await cast(Awaitable[object], raw_awaitable)
        except asyncio.CancelledError:
            return failure_result(
                request,
                error_code="PWK-ASYNC-CANCELLED",
                category=FailureCategory.CANCELLED,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="async_executor",
                summary="asyncio task accepted cooperative cancellation",
            )
        except Exception as exc:
            return failure_result(
                request,
                error_code=type(exc).__name__,
                category=FailureCategory.INTERNAL,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="async_executor",
                summary=str(exc) or type(exc).__name__,
            )

        if isinstance(raw, TaskExecutionResult):
            return raw
        return TaskExecutionResult(output=raw)

    def _complete_execution(
        self,
        attempt_id: TaskAttemptId,
        task: asyncio.Task[TaskExecutionResult],
    ) -> None:
        try:
            result = task.result()
        except asyncio.CancelledError:
            with self._lock:
                execution = self._active.get(attempt_id)
                if execution is None:
                    return
                result = failure_result(
                    execution.request,
                    error_code="PWK-ASYNC-CANCELLED",
                    category=FailureCategory.CANCELLED,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    source_component="async_executor",
                    summary="asyncio task was cancelled",
                )
        except Exception as exc:
            with self._lock:
                execution = self._active.get(attempt_id)
                if execution is None:
                    return
                result = failure_result(
                    execution.request,
                    error_code=type(exc).__name__,
                    category=FailureCategory.INTERNAL,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    source_component="async_executor",
                    summary=str(exc) or type(exc).__name__,
                )

        with self._lock:
            execution = self._active.get(attempt_id)
            if execution is None:
                return
            execution.result = result
            execution.done_event.set()
            if execution.detached:
                self._active.pop(attempt_id, None)
                self._completed.add(attempt_id)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop_started.set()
        try:
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()
            self._loop_stopped.set()


def _remaining_seconds(request: TaskExecutionRequest) -> float | None:
    if request.deadline_at is None:
        return None
    now = datetime.now(tz=request.deadline_at.tzinfo)
    return max(0.0, (request.deadline_at - now).total_seconds())


def _known_timeout(request: TaskExecutionRequest) -> TaskExecutionResult:
    return failure_result(
        request,
        error_code="PWK-ASYNC-DEADLINE-EXPIRED",
        category=FailureCategory.TIMEOUT,
        retryability=Retryability.RETRYABLE,
        uncertainty=OutcomeUncertainty.KNOWN,
        source_component="async_executor",
        summary="async execution deadline expired before coroutine scheduling",
    )


def _soft_timeout(request: TaskExecutionRequest) -> TaskExecutionResult:
    return failure_result(
        request,
        error_code="PWK-ASYNC-SOFT-TIMEOUT",
        category=FailureCategory.TIMEOUT,
        retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
        uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
        source_component="async_executor",
        summary="async execution exceeded its deadline and cancellation is cooperative",
    )


_protocol_probe = AsyncExecutor(max_concurrency=1)
try:
    if not isinstance(_protocol_probe, Executor):
        raise TypeError("AsyncExecutor must satisfy Executor")
    if not isinstance(_protocol_probe, CancellableExecutor):
        raise TypeError("AsyncExecutor must satisfy CancellableExecutor")
finally:
    _protocol_probe.shutdown()


__all__ = ["AsyncExecutor"]
