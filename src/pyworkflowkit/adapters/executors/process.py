"""Bounded process executor with explicit transport and hard termination semantics."""

from __future__ import annotations

import logging
import pickle
from contextlib import suppress
from dataclasses import dataclass
from multiprocessing import get_all_start_methods, get_context
from multiprocessing.connection import Connection
from multiprocessing.context import BaseContext
from multiprocessing.process import BaseProcess
from threading import RLock, Thread

from pyworkflowkit.adapters.executors._python import (
    invoke_python_handler,
    resolve_invocation_arity,
)
from pyworkflowkit.application.completion import (
    AttemptCompletion,
    CompletionQueue,
    ExecutionHandle,
)
from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.ids import (
    ArtifactId,
    ExternalRunRefId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef, TaskResult
from pyworkflowkit.errors import (
    DuplicateExecutionSubmissionError,
    ExecutionHandleNotFoundError,
    ExecutionTimeoutError,
    ExecutorError,
    ExecutorSerializationError,
    ExecutorShutdownError,
    ExecutorWorkerError,
    InvalidHandlerError,
    TaskExecutionError,
)
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    ExecutorCapabilities,
    RunContext,
    TaskHandler,
    TimeoutCapability,
)

logger = logging.getLogger("pyworkflowkit.executor.process")


@dataclass(frozen=True, slots=True)
class _TaskSnapshot:
    task_id: str
    handler_ref: str | None


@dataclass(frozen=True, slots=True)
class _RunContextSnapshot:
    workflow_run_id: str
    task_run_id: str
    attempt_id: str
    task_id: str
    attempt_number: int
    workflow_parameters: dict[str, object]
    dependency_outputs: dict[str, object]


@dataclass(frozen=True, slots=True)
class _ArtifactSnapshot:
    artifact_id: str
    name: str
    uri: str
    media_type: str | None
    checksum: str | None
    size_bytes: int | None
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class _ExternalRefSnapshot:
    external_ref_id: str
    provider: str
    external_run_id: str
    uri: str | None
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class _TaskResultSnapshot:
    output: object | None
    metadata: dict[str, object]
    artifacts: tuple[_ArtifactSnapshot, ...]
    external_refs: tuple[_ExternalRefSnapshot, ...]


@dataclass(frozen=True, slots=True)
class _ErrorSnapshot:
    kind: str
    error_type: str
    error_message: str
    error_category: str | None = None


@dataclass(frozen=True, slots=True)
class _WorkerMessage:
    result: _TaskResultSnapshot | None = None
    error: _ErrorSnapshot | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.error is None):
            raise ValueError("_WorkerMessage requires exactly one of result or error")


@dataclass(slots=True)
class _ActiveProcess:
    handle: ExecutionHandle
    process: BaseProcess
    receive_connection: Connection
    watcher: Thread


def _task_snapshot(task: TaskDefinition) -> _TaskSnapshot:
    return _TaskSnapshot(task_id=str(task.task_id), handler_ref=task.handler_ref)


def _context_snapshot(context: RunContext) -> _RunContextSnapshot:
    return _RunContextSnapshot(
        workflow_run_id=str(context.workflow_run_id),
        task_run_id=str(context.task_run_id),
        attempt_id=str(context.attempt_id),
        task_id=str(context.task_id),
        attempt_number=context.attempt_number,
        workflow_parameters=dict(context.workflow_parameters),
        dependency_outputs={
            str(task_id): value for task_id, value in context.dependency_outputs.items()
        },
    )


def _restore_task(snapshot: _TaskSnapshot) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(snapshot.task_id),
        handler_ref=snapshot.handler_ref,
        executor_key="process",
    )


def _restore_context(snapshot: _RunContextSnapshot) -> RunContext:
    return RunContext(
        workflow_run_id=WorkflowRunId(snapshot.workflow_run_id),
        task_run_id=TaskRunId(snapshot.task_run_id),
        attempt_id=TaskAttemptId(snapshot.attempt_id),
        task_id=TaskId(snapshot.task_id),
        attempt_number=snapshot.attempt_number,
        workflow_parameters=snapshot.workflow_parameters,
        dependency_outputs={
            TaskId(task_id): value for task_id, value in snapshot.dependency_outputs.items()
        },
    )


def _result_snapshot(result: TaskResult) -> _TaskResultSnapshot:
    return _TaskResultSnapshot(
        output=result.output,
        metadata=dict(result.metadata),
        artifacts=tuple(
            _ArtifactSnapshot(
                artifact_id=str(artifact.artifact_id),
                name=artifact.name,
                uri=artifact.uri,
                media_type=artifact.media_type,
                checksum=artifact.checksum,
                size_bytes=artifact.size_bytes,
                metadata=dict(artifact.metadata),
            )
            for artifact in result.artifacts
        ),
        external_refs=tuple(
            _ExternalRefSnapshot(
                external_ref_id=str(reference.external_ref_id),
                provider=reference.provider,
                external_run_id=reference.external_run_id,
                uri=reference.uri,
                metadata=dict(reference.metadata),
            )
            for reference in result.external_refs
        ),
    )


def _restore_result(snapshot: _TaskResultSnapshot) -> TaskResult:
    return TaskResult(
        output=snapshot.output,
        metadata=snapshot.metadata,
        artifacts=tuple(
            ArtifactReference(
                artifact_id=ArtifactId(artifact.artifact_id),
                name=artifact.name,
                uri=artifact.uri,
                media_type=artifact.media_type,
                checksum=artifact.checksum,
                size_bytes=artifact.size_bytes,
                metadata=artifact.metadata,
            )
            for artifact in snapshot.artifacts
        ),
        external_refs=tuple(
            ExternalRunRef(
                external_ref_id=ExternalRunRefId(reference.external_ref_id),
                provider=reference.provider,
                external_run_id=reference.external_run_id,
                uri=reference.uri,
                metadata=reference.metadata,
            )
            for reference in snapshot.external_refs
        ),
    )


def _ensure_picklable(value: object, *, object_name: str) -> None:
    try:
        pickle.dumps(value)
    except Exception as exc:
        raise ExecutorSerializationError(
            executor_key="process",
            object_name=object_name,
            error_type=type(exc).__name__,
            error_message=str(exc) or type(exc).__name__,
        ) from exc


def _worker_main(
    send_connection: Connection,
    task_snapshot: _TaskSnapshot,
    handler: TaskHandler,
    context_snapshot: _RunContextSnapshot,
) -> None:
    try:
        task = _restore_task(task_snapshot)
        context = _restore_context(context_snapshot)

        try:
            result = invoke_python_handler(
                task=task,
                handler=handler,
                context=context,
                executor_key="process",
                logger=logger,
            )
            snapshot = _result_snapshot(result)
            try:
                pickle.dumps(snapshot)
            except Exception as exc:
                message = _WorkerMessage(
                    error=_ErrorSnapshot(
                        kind="serialization",
                        error_type=type(exc).__name__,
                        error_message=str(exc) or type(exc).__name__,
                    )
                )
            else:
                message = _WorkerMessage(result=snapshot)
        except TaskExecutionError as exc:
            message = _WorkerMessage(
                error=_ErrorSnapshot(
                    kind="task",
                    error_type=exc.error_type,
                    error_message=exc.error_message,
                    error_category=exc.error_category,
                )
            )
        except ExecutorError as exc:
            message = _WorkerMessage(
                error=_ErrorSnapshot(
                    kind="worker",
                    error_type=type(exc).__name__,
                    error_message=str(exc) or type(exc).__name__,
                )
            )
        except BaseException as exc:
            message = _WorkerMessage(
                error=_ErrorSnapshot(
                    kind="worker",
                    error_type=type(exc).__name__,
                    error_message=str(exc) or type(exc).__name__,
                )
            )

        send_connection.send(message)
    finally:
        send_connection.close()


def _completion_from_message(
    *,
    handle: ExecutionHandle,
    task: TaskDefinition,
    message: _WorkerMessage,
) -> AttemptCompletion:
    if message.result is not None:
        return AttemptCompletion(handle=handle, result=_restore_result(message.result))

    if message.error is None:
        return AttemptCompletion(
            handle=handle,
            error=ExecutorWorkerError(
                executor_key="process",
                error_type="InvalidWorkerMessage",
                error_message="worker returned neither a result nor an error",
            ),
        )

    error = message.error
    if error.kind == "task":
        return AttemptCompletion(
            handle=handle,
            error=TaskExecutionError(
                task_id=task.task_id,
                handler_ref=task.handler_ref,
                error_type=error.error_type,
                error_message=error.error_message,
                error_category=error.error_category,
            ),
        )
    if error.kind == "serialization":
        return AttemptCompletion(
            handle=handle,
            error=ExecutorSerializationError(
                executor_key="process",
                object_name="task result",
                error_type=error.error_type,
                error_message=error.error_message,
            ),
        )
    return AttemptCompletion(
        handle=handle,
        error=ExecutorWorkerError(
            executor_key="process",
            error_type=error.error_type,
            error_message=error.error_message,
        ),
    )


class ProcessExecutor:
    """Execute trusted Python handlers in isolated, bounded child processes.

    Each active handle owns one child process. The bounded active-process set provides
    process-pool capacity while retaining per-handle termination on Python 3.11-3.13.
    """

    def __init__(
        self,
        *,
        max_workers: int = 2,
        start_method: str = "spawn",
        completion_queue: CompletionQueue | None = None,
        terminate_grace_seconds: float = 0.2,
    ) -> None:
        if isinstance(max_workers, bool) or not isinstance(max_workers, int):
            raise TypeError("max_workers must be an integer")
        if max_workers < 1:
            raise ValueError("max_workers must be greater than or equal to 1")
        if start_method not in get_all_start_methods():
            raise ValueError(f"unsupported multiprocessing start method: {start_method!r}")
        if isinstance(terminate_grace_seconds, bool) or not isinstance(
            terminate_grace_seconds, (int, float)
        ):
            raise TypeError("terminate_grace_seconds must be a number")
        if terminate_grace_seconds < 0:
            raise ValueError("terminate_grace_seconds must be greater than or equal to 0")

        self._max_workers = max_workers
        self._mp_context: BaseContext = get_context(start_method)
        self._completion_queue = (
            completion_queue if completion_queue is not None else CompletionQueue()
        )
        self._terminate_grace_seconds = float(terminate_grace_seconds)
        self._capabilities = ExecutorCapabilities(
            supports_parallelism=True,
            timeout=TimeoutCapability.HARD,
            cancellation=CancellationCapability.HARD,
            max_concurrency=max_workers,
        )
        self._active: dict[str, _ActiveProcess] = {}
        self._handles: dict[str, ExecutionHandle] = {}
        self._completed_handle_ids: set[str] = set()
        self._submitted_attempt_ids: set[TaskAttemptId] = set()
        self._shutdown = False
        self._lock = RLock()

    @property
    def key(self) -> str:
        return "process"

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
        """Synchronously execute one handler in a dedicated child process."""

        self._validate_submission(task=task, handler=handler, context=context)
        receive_connection, send_connection = self._mp_context.Pipe(duplex=False)
        process = self._mp_context.Process(
            target=_worker_main,
            args=(send_connection, _task_snapshot(task), handler, _context_snapshot(context)),
            name=f"pyworkflowkit-{context.attempt_id}",
        )
        process.start()
        send_connection.close()

        try:
            if task.timeout_seconds is None or receive_connection.poll(task.timeout_seconds):
                message = receive_connection.recv()
            else:
                self._terminate_process(process)
                raise ExecutionTimeoutError(
                    task_id=task.task_id,
                    handler_ref=task.handler_ref,
                    timeout_seconds=task.timeout_seconds,
                    timeout_mode=task.timeout_mode.value,
                )
        except EOFError as exc:
            raise ExecutorWorkerError(
                executor_key=self.key,
                error_type="ProcessExitedWithoutResult",
                error_message=f"child process exited with code {process.exitcode}",
            ) from exc
        finally:
            receive_connection.close()
            process.join()
            process.close()

        handle = ExecutionHandle(
            handle_id=f"{self.key}:{context.attempt_id}",
            attempt_id=context.attempt_id,
            executor_key=self.key,
        )
        completion = _completion_from_message(handle=handle, task=task, message=message)
        if completion.result is not None:
            return completion.result
        if completion.error is None:
            raise ExecutorWorkerError(
                executor_key=self.key,
                error_type="InvalidCompletion",
                error_message="process completion did not contain a result or error",
            )
        raise completion.error

    def submit(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> ExecutionHandle:
        """Submit one TaskAttempt to an isolated process and return immediately."""

        self._validate_submission(task=task, handler=handler, context=context)
        handle = ExecutionHandle(
            handle_id=f"{self.key}:{context.attempt_id}",
            attempt_id=context.attempt_id,
            executor_key=self.key,
        )
        receive_connection, send_connection = self._mp_context.Pipe(duplex=False)
        process = self._mp_context.Process(
            target=_worker_main,
            args=(send_connection, _task_snapshot(task), handler, _context_snapshot(context)),
            name=f"pyworkflowkit-{context.attempt_id}",
        )

        with self._lock:
            if self._shutdown:
                receive_connection.close()
                send_connection.close()
                raise ExecutorShutdownError(executor_key=self.key)
            if context.attempt_id in self._submitted_attempt_ids:
                receive_connection.close()
                send_connection.close()
                raise DuplicateExecutionSubmissionError(
                    executor_key=self.key,
                    attempt_id=str(context.attempt_id),
                )
            if len(self._active) >= self._max_workers:
                receive_connection.close()
                send_connection.close()
                raise ExecutorWorkerError(
                    executor_key=self.key,
                    error_type="ProcessCapacityExceeded",
                    error_message=(
                        f"active process capacity {self._max_workers} is already saturated"
                    ),
                )

            process.start()
            send_connection.close()
            watcher = Thread(
                target=self._watch_process,
                args=(handle, task, process, receive_connection),
                name=f"pyworkflowkit-process-watch-{context.attempt_id}",
                daemon=True,
            )
            self._submitted_attempt_ids.add(context.attempt_id)
            self._handles[handle.handle_id] = handle
            self._active[handle.handle_id] = _ActiveProcess(
                handle=handle,
                process=process,
                receive_connection=receive_connection,
                watcher=watcher,
            )
            watcher.start()

        return handle

    def wait(
        self,
        handle: ExecutionHandle,
        *,
        timeout: float | None = None,
    ) -> bool:
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be greater than or equal to 0")
        with self._lock:
            process = self._process_for_wait(handle)
            if process is None:
                return True
            process.join(timeout=timeout)
            return not process.is_alive()

    def terminate(self, handle: ExecutionHandle) -> bool:
        """Hard-stop one active execution handle when it still owns a live process."""

        with self._lock:
            process = self._process_for_wait(handle)
            if process is None or not process.is_alive():
                return False
            self._terminate_process(process)
            return True

    def active_handles(self) -> tuple[ExecutionHandle, ...]:
        with self._lock:
            return tuple(
                self._handles[handle_id]
                for handle_id in sorted(self._active)
            )

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._shutdown = True
            active = tuple(self._active.values())
            if not wait:
                for execution in active:
                    with suppress(ValueError):
                        if execution.process.is_alive():
                            self._terminate_process(execution.process)

        for execution in active:
            with suppress(ValueError):
                execution.process.join()
        for execution in active:
            execution.watcher.join()

    def __enter__(self) -> ProcessExecutor:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.shutdown(wait=True)

    def _validate_submission(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> None:
        if task.executor_key != self.key:
            raise InvalidHandlerError(
                task_id=task.task_id,
                reason=(
                    f"task requests executor '{task.executor_key}', "
                    f"but executor key is '{self.key}'"
                ),
            )
        resolve_invocation_arity(task=task, handler=handler)
        _ensure_picklable(handler, object_name="handler")
        _ensure_picklable(_task_snapshot(task), object_name="task transport")
        _ensure_picklable(_context_snapshot(context), object_name="RunContext transport")

    def _watch_process(
        self,
        handle: ExecutionHandle,
        task: TaskDefinition,
        process: BaseProcess,
        receive_connection: Connection,
    ) -> None:
        try:
            try:
                message = receive_connection.recv()
            except EOFError:
                completion = AttemptCompletion(
                    handle=handle,
                    error=ExecutorWorkerError(
                        executor_key=self.key,
                        error_type="ProcessExitedWithoutResult",
                        error_message=f"child process exited with code {process.exitcode}",
                    ),
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
            else:
                completion = _completion_from_message(
                    handle=handle,
                    task=task,
                    message=message,
                )
            process.join()
        finally:
            receive_connection.close()
            with self._lock:
                self._active.pop(handle.handle_id, None)
                self._completed_handle_ids.add(handle.handle_id)
                with suppress(ValueError):
                    process.close()

        self._completion_queue.put(completion)

    def _process_for_wait(self, handle: ExecutionHandle) -> BaseProcess | None:
        with self._lock:
            registered = self._handles.get(handle.handle_id)
            if registered is None or registered != handle:
                raise ExecutionHandleNotFoundError(
                    executor_key=self.key,
                    handle_id=handle.handle_id,
                )
            if handle.handle_id in self._completed_handle_ids:
                return None
            execution = self._active.get(handle.handle_id)
            if execution is None:
                raise ExecutionHandleNotFoundError(
                    executor_key=self.key,
                    handle_id=handle.handle_id,
                )
            return execution.process

    def _terminate_process(self, process: BaseProcess) -> None:
        if not process.is_alive():
            return
        process.terminate()
        process.join(timeout=self._terminate_grace_seconds)
        if process.is_alive():
            kill = getattr(process, "kill", None)
            if kill is not None:
                kill()
                process.join()


__all__ = ["ProcessExecutor"]
