"""Thread-pool executor with completion transfer and soft-wait semantics."""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import wait as wait_futures
from functools import partial
from threading import RLock

from pyworkflowkit.adapters.executors._python import invoke_python_handler
from pyworkflowkit.application.completion import (
    AttemptCompletion,
    CompletionQueue,
    ExecutionHandle,
)
from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.ids import TaskAttemptId
from pyworkflowkit.domain.values import TaskResult
from pyworkflowkit.errors import (
    DuplicateExecutionSubmissionError,
    ExecutionHandleNotFoundError,
    ExecutorError,
    ExecutorShutdownError,
    ExecutorWorkerError,
)
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    ExecutorCapabilities,
    RunContext,
    TaskHandler,
    TimeoutCapability,
)

logger = logging.getLogger("pyworkflowkit.executor.thread")


class ThreadExecutor:
    """Execute trusted Python handlers using a bounded ThreadPoolExecutor."""

    def __init__(
        self,
        *,
        max_workers: int = 4,
        thread_name_prefix: str = "pyworkflowkit",
        completion_queue: CompletionQueue | None = None,
    ) -> None:
        if isinstance(max_workers, bool) or not isinstance(max_workers, int):
            raise TypeError("max_workers must be an integer")
        if max_workers < 1:
            raise ValueError("max_workers must be greater than or equal to 1")
        if not thread_name_prefix.strip():
            raise ValueError("thread_name_prefix must not be blank")

        self._max_workers = max_workers
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        self._completion_queue = completion_queue if completion_queue is not None else CompletionQueue()
        self._capabilities = ExecutorCapabilities(
            supports_parallelism=True,
            timeout=TimeoutCapability.SOFT,
            cancellation=CancellationCapability.NONE,
            max_concurrency=max_workers,
        )
        self._active_futures: dict[str, Future[TaskResult]] = {}
        self._handles: dict[str, ExecutionHandle] = {}
        self._completed_handle_ids: set[str] = set()
        self._submitted_attempt_ids: set[TaskAttemptId] = set()
        self._shutdown = False
        self._lock = RLock()

    @property
    def key(self) -> str:
        return "thread"

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

    def execute(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> TaskResult:
        """Execute synchronously in the current thread.

        Pool workers call this method so ThreadExecutor continues to satisfy the
        existing Executor protocol.
        """

        return invoke_python_handler(
            task=task,
            handler=handler,
            context=context,
            executor_key=self.key,
            logger=logger,
        )

    def submit(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> ExecutionHandle:
        """Submit one TaskAttempt to the thread pool and return immediately."""

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

            future = self._pool.submit(
                self.execute,
                task=task,
                handler=handler,
                context=context,
            )
            self._submitted_attempt_ids.add(context.attempt_id)
            self._handles[handle.handle_id] = handle
            self._active_futures[handle.handle_id] = future
            future.add_done_callback(partial(self._publish_completion, handle))

        return handle

    def wait(
        self,
        handle: ExecutionHandle,
        *,
        timeout: float | None = None,
    ) -> bool:
        """Wait softly for one handle.

        False means only that the wait timed out. The underlying thread keeps
        running and will still publish its completion.
        """

        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be greater than or equal to 0")

        future = self._future_for_wait(handle)
        if future is None:
            return True

        done, _ = wait_futures((future,), timeout=timeout)
        return bool(done)

    def active_handles(self) -> tuple[ExecutionHandle, ...]:
        with self._lock:
            return tuple(self._handles[handle_id] for handle_id in sorted(self._active_futures))

    def shutdown(self, *, wait: bool = True) -> None:
        """Stop accepting submissions and shut down the underlying thread pool."""

        with self._lock:
            self._shutdown = True
        self._pool.shutdown(wait=wait, cancel_futures=False)

    def __enter__(self) -> ThreadExecutor:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.shutdown(wait=True)

    def _future_for_wait(
        self,
        handle: ExecutionHandle,
    ) -> Future[TaskResult] | None:
        with self._lock:
            registered = self._handles.get(handle.handle_id)
            if registered is None or registered != handle:
                raise ExecutionHandleNotFoundError(
                    executor_key=self.key,
                    handle_id=handle.handle_id,
                )
            if handle.handle_id in self._completed_handle_ids:
                return None
            future = self._active_futures.get(handle.handle_id)
            if future is None:
                raise ExecutionHandleNotFoundError(
                    executor_key=self.key,
                    handle_id=handle.handle_id,
                )
            return future

    def _publish_completion(
        self,
        handle: ExecutionHandle,
        future: Future[TaskResult],
    ) -> None:
        try:
            completion = AttemptCompletion(
                handle=handle,
                result=future.result(),
            )
        except ExecutorError as exc:
            completion = AttemptCompletion(
                handle=handle,
                error=exc,
            )
        except BaseException as exc:
            completion = AttemptCompletion(
                handle=handle,
                error=ExecutorWorkerError(
                    executor_key=self.key,
                    error_type=type(exc).__name__,
                    error_message=str(exc) or type(exc).__name__,
                ),
            )

        with self._lock:
            self._active_futures.pop(handle.handle_id, None)
            self._completed_handle_ids.add(handle.handle_id)

        self._completion_queue.put(completion)


__all__ = ["ThreadExecutor"]
