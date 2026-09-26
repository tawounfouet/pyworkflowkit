"""Asyncio executor with explicit awaitable workloads and cooperative cancellation."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from contextlib import suppress
from functools import partial
from inspect import isawaitable
from threading import Event, RLock, Thread, current_thread
from typing import cast

from pyworkflowkit.adapters.executors._python import normalize_result, resolve_invocation_arity
from pyworkflowkit.application.completion import (
    AttemptCompletion,
    CompletionQueue,
    ExecutionHandle,
)
from pyworkflowkit.application.observability import LogContext, log_runtime
from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.ids import TaskAttemptId
from pyworkflowkit.domain.values import TaskResult
from pyworkflowkit.errors import (
    DuplicateExecutionSubmissionError,
    ExecutionHandleNotFoundError,
    ExecutorError,
    ExecutorShutdownError,
    ExecutorWorkerError,
    InvalidHandlerError,
    TaskExecutionError,
)
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    ContextHandler,
    ExecutorCapabilities,
    RunContext,
    TaskHandler,
    TimeoutCapability,
    ZeroArgumentHandler,
)

logger = logging.getLogger("pyworkflowkit.executor.async")


async def _invoke_async_handler(
    *,
    task: TaskDefinition,
    handler: TaskHandler,
    context: RunContext,
    executor_key: str,
) -> TaskResult:
    """Invoke one awaitable Python handler and normalize its result."""

    if task.executor_key != executor_key:
        raise InvalidHandlerError(
            task_id=task.task_id,
            reason=(
                f"task requests executor '{task.executor_key}', "
                f"but executor key is '{executor_key}'"
            ),
        )

    invocation_arity = resolve_invocation_arity(task=task, handler=handler)
    log_context = LogContext(
        run_id=str(context.workflow_run_id),
        task_run_id=str(context.task_run_id),
        task_id=str(context.task_id),
        attempt_number=context.attempt_number,
        executor_key=executor_key,
    )
    log_runtime(logger, logging.DEBUG, "Async executor invocation started", context=log_context)

    try:
        if invocation_arity == 0:
            raw_awaitable = cast(ZeroArgumentHandler, handler)()
        else:
            raw_awaitable = cast(ContextHandler, handler)(context)

        if not isawaitable(raw_awaitable):
            raise InvalidHandlerError(
                task_id=task.task_id,
                reason="AsyncExecutor handler must return an awaitable",
            )

        raw_result = await cast(Awaitable[object], raw_awaitable)
    except asyncio.CancelledError:
        log_runtime(
            logger,
            logging.INFO,
            "Async executor invocation cancelled",
            context=log_context,
        )
        raise
    except ExecutorError:
        raise
    except Exception as exc:
        log_runtime(
            logger,
            logging.WARNING,
            "Async executor invocation failed",
            context=log_context,
            fields={"error_type": type(exc).__name__},
        )
        raise TaskExecutionError(
            task_id=task.task_id,
            handler_ref=task.handler_ref,
            error_type=type(exc).__name__,
            error_message=str(exc),
            error_category=type(exc).__name__,
        ) from exc

    result = normalize_result(raw_result)
    log_runtime(logger, logging.DEBUG, "Async executor invocation succeeded", context=log_context)
    return result


class AsyncExecutor:
    """Execute awaitable trusted-Python handlers on a dedicated asyncio event loop."""

    def __init__(
        self,
        *,
        max_concurrency: int = 100,
        loop_thread_name: str = "pyworkflowkit-async",
        completion_queue: CompletionQueue | None = None,
    ) -> None:
        if isinstance(max_concurrency, bool) or not isinstance(max_concurrency, int):
            raise TypeError("max_concurrency must be an integer")
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be greater than or equal to 1")
        if not loop_thread_name.strip():
            raise ValueError("loop_thread_name must not be blank")

        self._max_concurrency = max_concurrency
        self._completion_queue = (
            completion_queue if completion_queue is not None else CompletionQueue()
        )
        self._capabilities = ExecutorCapabilities(
            supports_parallelism=True,
            timeout=TimeoutCapability.SOFT,
            cancellation=CancellationCapability.COOPERATIVE,
            max_concurrency=max_concurrency,
            supports_async=True,
        )

        self._loop = asyncio.new_event_loop()
        self._loop_started = Event()
        self._loop_stopped = Event()
        self._loop_thread = Thread(
            target=self._run_loop,
            name=loop_thread_name,
            daemon=True,
        )

        self._active_handles: dict[str, ExecutionHandle] = {}
        self._async_tasks: dict[str, asyncio.Task[TaskResult]] = {}
        self._done_events: dict[str, Event] = {}
        self._handles: dict[str, ExecutionHandle] = {}
        self._completed_handle_ids: set[str] = set()
        self._pending_cancellations: set[str] = set()
        self._submitted_attempt_ids: set[TaskAttemptId] = set()
        self._shutdown = False
        self._stop_when_idle = False
        self._lock = RLock()

        self._loop_thread.start()
        self._loop_started.wait()

    @property
    def key(self) -> str:
        return "async"

    @property
    def capabilities(self) -> ExecutorCapabilities:
        return self._capabilities

    @property
    def completion_queue(self) -> CompletionQueue:
        return self._completion_queue

    @property
    def is_shutdown(self) -> bool:
        with self._lock:
            return self._shutdown

    async def execute_async(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> TaskResult:
        """Natively await one async handler."""

        return await _invoke_async_handler(
            task=task,
            handler=handler,
            context=context,
            executor_key=self.key,
        )

    def execute(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> TaskResult:
        """Compatibility bridge for the historical synchronous Executor port.

        Native async callers should prefer execute_async(). ConcurrentRunner uses
        submit() and therefore never blocks the event-loop thread through this bridge.
        """

        if current_thread() is self._loop_thread:
            raise InvalidHandlerError(
                task_id=task.task_id,
                reason="execute() cannot block the AsyncExecutor event-loop thread",
            )

        with self._lock:
            if self._shutdown:
                raise ExecutorShutdownError(executor_key=self.key)

        future = asyncio.run_coroutine_threadsafe(
            self.execute_async(task=task, handler=handler, context=context),
            self._loop,
        )
        try:
            return future.result()
        except ExecutorError:
            raise
        except BaseException as exc:
            raise ExecutorWorkerError(
                executor_key=self.key,
                error_type=type(exc).__name__,
                error_message=str(exc) or type(exc).__name__,
            ) from exc

    def submit(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> ExecutionHandle:
        """Schedule one async TaskAttempt and return its execution handle."""

        resolve_invocation_arity(task=task, handler=handler)
        if task.executor_key != self.key:
            raise InvalidHandlerError(
                task_id=task.task_id,
                reason=(
                    f"task requests executor '{task.executor_key}', "
                    f"but executor key is '{self.key}'"
                ),
            )

        handle = ExecutionHandle(
            handle_id=f"{self.key}:{context.attempt_id}",
            attempt_id=context.attempt_id,
            executor_key=self.key,
        )

        with self._lock:
            if self._shutdown:
                raise ExecutorShutdownError(executor_key=self.key)
            if context.attempt_id in self._submitted_attempt_ids:
                raise DuplicateExecutionSubmissionError(
                    executor_key=self.key,
                    attempt_id=str(context.attempt_id),
                )
            if len(self._active_handles) >= self._max_concurrency:
                raise ExecutorWorkerError(
                    executor_key=self.key,
                    error_type="AsyncCapacityExceeded",
                    error_message=(
                        f"active async capacity {self._max_concurrency} is already saturated"
                    ),
                )

            self._submitted_attempt_ids.add(context.attempt_id)
            self._handles[handle.handle_id] = handle
            self._active_handles[handle.handle_id] = handle
            self._done_events[handle.handle_id] = Event()

        try:
            self._loop.call_soon_threadsafe(
                self._schedule_task,
                handle,
                task,
                handler,
                context,
            )
        except RuntimeError as exc:
            self._publish_scheduling_failure(handle=handle, error=exc)

        return handle

    def cancel(self, handle: ExecutionHandle) -> bool:
        """Request cooperative asyncio.Task cancellation for one active handle."""

        with self._lock:
            registered = self._handles.get(handle.handle_id)
            if registered is None or registered != handle:
                raise ExecutionHandleNotFoundError(
                    executor_key=self.key,
                    handle_id=handle.handle_id,
                )
            if handle.handle_id in self._completed_handle_ids:
                return False

        acknowledged = Event()
        outcome: list[bool] = []

        def request_cancellation() -> None:
            with self._lock:
                if handle.handle_id in self._completed_handle_ids:
                    outcome.append(False)
                elif handle.handle_id not in self._active_handles:
                    outcome.append(False)
                else:
                    async_task = self._async_tasks.get(handle.handle_id)
                    if async_task is None:
                        self._pending_cancellations.add(handle.handle_id)
                        outcome.append(True)
                    elif async_task.done():
                        outcome.append(False)
                    else:
                        outcome.append(async_task.cancel())
            acknowledged.set()

        try:
            self._loop.call_soon_threadsafe(request_cancellation)
        except RuntimeError as exc:
            raise ExecutorWorkerError(
                executor_key=self.key,
                error_type=type(exc).__name__,
                error_message=str(exc) or type(exc).__name__,
            ) from exc

        acknowledged.wait()
        return outcome[0]

    def wait(
        self,
        handle: ExecutionHandle,
        *,
        timeout: float | None = None,
    ) -> bool:
        """Wait for the physical asyncio task to finish."""

        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be greater than or equal to 0")

        with self._lock:
            registered = self._handles.get(handle.handle_id)
            if registered is None or registered != handle:
                raise ExecutionHandleNotFoundError(
                    executor_key=self.key,
                    handle_id=handle.handle_id,
                )
            if handle.handle_id in self._completed_handle_ids:
                return True
            done_event = self._done_events[handle.handle_id]

        return done_event.wait(timeout=timeout)

    def active_handles(self) -> tuple[ExecutionHandle, ...]:
        with self._lock:
            return tuple(
                self._active_handles[handle_id]
                for handle_id in sorted(self._active_handles)
            )

    def shutdown(self, *, wait: bool = True) -> None:
        """Stop accepting work and close the event loop after active tasks settle."""

        with self._lock:
            self._shutdown = True
            active_handles = tuple(self._active_handles.values())
            done_events = tuple(
                self._done_events[handle.handle_id] for handle in active_handles
            )

        if wait:
            for done_event in done_events:
                done_event.wait()
            self._request_loop_stop()
            self._loop_thread.join()
            return

        for handle in active_handles:
            with suppress(ExecutionHandleNotFoundError, ExecutorWorkerError):
                self.cancel(handle)

        with self._lock:
            self._stop_when_idle = True
            idle = not self._active_handles

        if idle:
            self._request_loop_stop()

    def __enter__(self) -> AsyncExecutor:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.shutdown(wait=True)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop_started.set()
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()
            self._loop_stopped.set()

    def _schedule_task(
        self,
        handle: ExecutionHandle,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> None:
        try:
            async_task = self._loop.create_task(
                self.execute_async(task=task, handler=handler, context=context),
                name=f"pyworkflowkit-{context.attempt_id}",
            )
        except BaseException as exc:
            self._publish_scheduling_failure(handle=handle, error=exc)
            return

        with self._lock:
            if handle.handle_id not in self._active_handles:
                async_task.cancel()
                return
            self._async_tasks[handle.handle_id] = async_task
            should_cancel = handle.handle_id in self._pending_cancellations

        async_task.add_done_callback(partial(self._publish_completion, handle))
        if should_cancel:
            async_task.cancel()

    def _publish_completion(
        self,
        handle: ExecutionHandle,
        async_task: asyncio.Task[TaskResult],
    ) -> None:
        try:
            completion = AttemptCompletion(
                handle=handle,
                result=async_task.result(),
            )
        except asyncio.CancelledError:
            completion = AttemptCompletion(
                handle=handle,
                error=ExecutorWorkerError(
                    executor_key=self.key,
                    error_type="CancelledError",
                    error_message="async task was cancelled",
                ),
            )
        except ExecutorError as exc:
            completion = AttemptCompletion(handle=handle, error=exc)
        except BaseException as exc:
            completion = AttemptCompletion(
                handle=handle,
                error=ExecutorWorkerError(
                    executor_key=self.key,
                    error_type=type(exc).__name__,
                    error_message=str(exc) or type(exc).__name__,
                ),
            )

        self._finish_handle(handle=handle, completion=completion)

    def _publish_scheduling_failure(
        self,
        *,
        handle: ExecutionHandle,
        error: BaseException,
    ) -> None:
        completion = AttemptCompletion(
            handle=handle,
            error=ExecutorWorkerError(
                executor_key=self.key,
                error_type=type(error).__name__,
                error_message=str(error) or type(error).__name__,
            ),
        )
        self._finish_handle(handle=handle, completion=completion)

    def _finish_handle(
        self,
        *,
        handle: ExecutionHandle,
        completion: AttemptCompletion,
    ) -> None:
        with self._lock:
            self._async_tasks.pop(handle.handle_id, None)
            self._active_handles.pop(handle.handle_id, None)
            self._pending_cancellations.discard(handle.handle_id)
            self._completed_handle_ids.add(handle.handle_id)
            done_event = self._done_events.get(handle.handle_id)
            should_stop = self._stop_when_idle and not self._active_handles

        if done_event is not None:
            done_event.set()
        self._completion_queue.put(completion)

        if should_stop:
            self._loop.stop()

    def _request_loop_stop(self) -> None:
        if self._loop_stopped.is_set():
            return
        with suppress(RuntimeError):
            self._loop.call_soon_threadsafe(self._loop.stop)


__all__ = ["AsyncExecutor"]
