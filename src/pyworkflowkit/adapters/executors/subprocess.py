"""External-program executor with shell-free argv and captured process evidence."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from subprocess import DEVNULL, PIPE, Popen, TimeoutExpired
from threading import Event, RLock, Thread
from types import MappingProxyType
from typing import cast

from pyworkflowkit.adapters.executors._python import resolve_invocation_arity
from pyworkflowkit.adapters.executors.subprocess_security import SubprocessSecurityPolicy
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
    SubprocessExecutionError,
    SubprocessSecurityError,
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

logger = logging.getLogger("pyworkflowkit.executor.subprocess")


@dataclass(frozen=True, slots=True)
class SubprocessCommand:
    """Immutable shell-free external command specification."""

    argv: tuple[str, ...]
    cwd: str | None = None
    env: Mapping[str, str] | None = None
    stdin: str | None = None
    encoding: str = "utf-8"

    def __post_init__(self) -> None:
        argv = tuple(self.argv)
        if not argv:
            raise ValueError("argv must contain at least one element")
        if any(not isinstance(value, str) for value in argv):
            raise TypeError("argv values must be strings")
        if not argv[0].strip():
            raise ValueError("argv[0] executable must not be blank")
        if any("\x00" in value for value in argv):
            raise ValueError("argv values must not contain NUL characters")
        if self.cwd is not None:
            if not isinstance(self.cwd, str):
                raise TypeError("cwd must be a string or None")
            if not self.cwd.strip():
                raise ValueError("cwd must not be blank")
            if "\x00" in self.cwd:
                raise ValueError("cwd must not contain NUL characters")
        if self.stdin is not None and not isinstance(self.stdin, str):
            raise TypeError("stdin must be a string or None")
        if not isinstance(self.encoding, str):
            raise TypeError("encoding must be a string")
        if not self.encoding.strip():
            raise ValueError("encoding must not be blank")

        frozen_env: Mapping[str, str] | None = None
        if self.env is not None:
            copied_env: dict[str, str] = {}
            for key, value in self.env.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise TypeError("env keys and values must be strings")
                if not key or "=" in key or "\x00" in key:
                    raise ValueError("env keys must be non-empty and contain neither '=' nor NUL")
                if "\x00" in value:
                    raise ValueError("env values must not contain NUL characters")
                copied_env[key] = value
            frozen_env = MappingProxyType(copied_env)

        object.__setattr__(self, "argv", argv)
        object.__setattr__(self, "env", frozen_env)


@dataclass(frozen=True, slots=True)
class SubprocessResult:
    """Captured result from one external program invocation."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(slots=True)
class _ActiveSubprocess:
    handle: ExecutionHandle
    done_event: Event
    process: Popen[str] | None = None
    watcher: Thread | None = None
    termination_requested: bool = False


def _resolve_command(
    *,
    task: TaskDefinition,
    handler: TaskHandler,
    context: RunContext,
) -> SubprocessCommand:
    if task.executor_key != "subprocess":
        raise InvalidHandlerError(
            task_id=task.task_id,
            reason=(
                f"task requests executor '{task.executor_key}', but executor key is 'subprocess'"
            ),
        )

    invocation_arity = resolve_invocation_arity(task=task, handler=handler)
    log_context = LogContext(
        run_id=str(context.workflow_run_id),
        task_run_id=str(context.task_run_id),
        task_id=str(context.task_id),
        attempt_number=context.attempt_number,
        executor_key="subprocess",
    )
    log_runtime(logger, logging.DEBUG, "Subprocess command resolution started", context=log_context)

    try:
        if invocation_arity == 0:
            raw_command = cast(ZeroArgumentHandler, handler)()
        else:
            raw_command = cast(ContextHandler, handler)(context)
    except ExecutorError:
        raise
    except Exception as exc:
        raise TaskExecutionError(
            task_id=task.task_id,
            handler_ref=task.handler_ref,
            error_type=type(exc).__name__,
            error_message=str(exc),
            error_category="subprocess_command",
        ) from exc

    if not isinstance(raw_command, SubprocessCommand):
        raise InvalidHandlerError(
            task_id=task.task_id,
            reason="SubprocessExecutor handler must return SubprocessCommand",
        )

    log_runtime(logger, logging.DEBUG, "Subprocess command resolved", context=log_context)
    return raw_command


class SubprocessExecutor:
    """Execute external programs with shell=False and captured output."""

    def __init__(
        self,
        *,
        max_workers: int = 4,
        completion_queue: CompletionQueue | None = None,
        terminate_grace_seconds: float = 0.2,
        security_policy: SubprocessSecurityPolicy | None = None,
    ) -> None:
        if isinstance(max_workers, bool) or not isinstance(max_workers, int):
            raise TypeError("max_workers must be an integer")
        if max_workers < 1:
            raise ValueError("max_workers must be greater than or equal to 1")
        if isinstance(terminate_grace_seconds, bool) or not isinstance(
            terminate_grace_seconds, (int, float)
        ):
            raise TypeError("terminate_grace_seconds must be a number")
        if terminate_grace_seconds < 0:
            raise ValueError("terminate_grace_seconds must be greater than or equal to 0")

        self._max_workers = max_workers
        self._completion_queue = (
            completion_queue if completion_queue is not None else CompletionQueue()
        )
        self._terminate_grace_seconds = float(terminate_grace_seconds)
        self._security_policy = security_policy or SubprocessSecurityPolicy()
        self._capabilities = ExecutorCapabilities(
            supports_parallelism=True,
            timeout=TimeoutCapability.HARD,
            cancellation=CancellationCapability.HARD,
            max_concurrency=max_workers,
        )
        self._active: dict[str, _ActiveSubprocess] = {}
        self._handles: dict[str, ExecutionHandle] = {}
        self._completed_handle_ids: set[str] = set()
        self._submitted_attempt_ids: set[TaskAttemptId] = set()
        self._shutdown = False
        self._lock = RLock()

    @property
    def key(self) -> str:
        return "subprocess"

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
        """Synchronously execute one external program.

        Runtime timeout coordination remains owned by ConcurrentRunner. Direct execute()
        waits for the child process to exit.
        """

        command = _resolve_command(task=task, handler=handler, context=context)
        self._validate_security(task=task, command=command)
        process = self._spawn(task=task, command=command)
        try:
            stdout, stderr = process.communicate(input=command.stdin)
        except BaseException:
            if process.poll() is None:
                self._terminate_process(process)
            raise

        self._validate_captured_security(
            task=task,
            command=command,
            stdout=stdout,
            stderr=stderr,
        )
        return self._result_or_error(
            task=task,
            command=command,
            returncode=cast(int, process.returncode),
            stdout=stdout,
            stderr=stderr,
        )

    def submit(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> ExecutionHandle:
        """Start one external program and return an ExecutionHandle."""

        handle = ExecutionHandle(
            handle_id=f"{self.key}:{context.attempt_id}",
            attempt_id=context.attempt_id,
            executor_key=self.key,
        )
        active = _ActiveSubprocess(handle=handle, done_event=Event())

        with self._lock:
            if self._shutdown:
                raise ExecutorShutdownError(executor_key=self.key)
            if context.attempt_id in self._submitted_attempt_ids:
                raise DuplicateExecutionSubmissionError(
                    executor_key=self.key,
                    attempt_id=str(context.attempt_id),
                )
            if len(self._active) >= self._max_workers:
                raise ExecutorWorkerError(
                    executor_key=self.key,
                    error_type="SubprocessCapacityExceeded",
                    error_message=(
                        f"active subprocess capacity {self._max_workers} is already saturated"
                    ),
                )
            self._submitted_attempt_ids.add(context.attempt_id)
            self._handles[handle.handle_id] = handle
            self._active[handle.handle_id] = active

        try:
            command = _resolve_command(task=task, handler=handler, context=context)
            self._validate_security(task=task, command=command)
            process = self._spawn(task=task, command=command)
        except ExecutorError as exc:
            self._finish_handle(
                handle=handle,
                completion=AttemptCompletion(handle=handle, error=exc),
            )
            return handle
        except BaseException as exc:
            self._finish_handle(
                handle=handle,
                completion=AttemptCompletion(
                    handle=handle,
                    error=ExecutorWorkerError(
                        executor_key=self.key,
                        error_type=type(exc).__name__,
                        error_message=str(exc) or type(exc).__name__,
                    ),
                ),
            )
            return handle

        watcher = Thread(
            target=self._watch_process,
            args=(handle, task, command, process),
            name=f"pyworkflowkit-subprocess-watch-{context.attempt_id}",
            daemon=True,
        )

        with self._lock:
            current = self._active.get(handle.handle_id)
            if current is None:
                self._terminate_process(process)
                return handle
            current.process = process
            current.watcher = watcher
            terminate_now = current.termination_requested

        if terminate_now:
            self._terminate_process(process)

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
            registered = self._handles.get(handle.handle_id)
            if registered is None or registered != handle:
                raise ExecutionHandleNotFoundError(
                    executor_key=self.key,
                    handle_id=handle.handle_id,
                )
            if handle.handle_id in self._completed_handle_ids:
                return True
            active = self._active.get(handle.handle_id)
            if active is None:
                raise ExecutionHandleNotFoundError(
                    executor_key=self.key,
                    handle_id=handle.handle_id,
                )
            done_event = active.done_event
        return done_event.wait(timeout=timeout)

    def terminate(self, handle: ExecutionHandle) -> bool:
        """Hard-stop one active child process owned by this executor."""

        with self._lock:
            registered = self._handles.get(handle.handle_id)
            if registered is None or registered != handle:
                raise ExecutionHandleNotFoundError(
                    executor_key=self.key,
                    handle_id=handle.handle_id,
                )
            if handle.handle_id in self._completed_handle_ids:
                return False
            active = self._active.get(handle.handle_id)
            if active is None:
                raise ExecutionHandleNotFoundError(
                    executor_key=self.key,
                    handle_id=handle.handle_id,
                )
            if active.process is None:
                active.termination_requested = True
                return True
            if active.process.poll() is not None:
                return False
            self._terminate_process(active.process)
            return True

    def active_handles(self) -> tuple[ExecutionHandle, ...]:
        with self._lock:
            return tuple(self._active[handle_id].handle for handle_id in sorted(self._active))

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._shutdown = True
            active_handles = tuple(execution.handle for execution in self._active.values())

        if not wait:
            for handle in active_handles:
                with suppress(ExecutionHandleNotFoundError):
                    self.terminate(handle)
            return

        for handle in active_handles:
            with suppress(ExecutionHandleNotFoundError):
                self.wait(handle)

        with self._lock:
            watchers = tuple(
                execution.watcher
                for execution in self._active.values()
                if execution.watcher is not None
            )
        for watcher in watchers:
            watcher.join()

    def __enter__(self) -> SubprocessExecutor:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.shutdown(wait=True)

    def _spawn(
        self,
        *,
        task: TaskDefinition,
        command: SubprocessCommand,
    ) -> Popen[str]:
        try:
            return Popen(
                command.argv,
                shell=False,
                cwd=command.cwd,
                env=self._security_policy.environment_for(command),
                stdin=PIPE if command.stdin is not None else DEVNULL,
                stdout=PIPE,
                stderr=PIPE,
                text=True,
                encoding=command.encoding,
            )
        except (OSError, ValueError, LookupError) as exc:
            raise TaskExecutionError(
                task_id=task.task_id,
                handler_ref=task.handler_ref,
                error_type=type(exc).__name__,
                error_message=str(exc),
                error_category="subprocess_spawn",
            ) from exc

    def _watch_process(
        self,
        handle: ExecutionHandle,
        task: TaskDefinition,
        command: SubprocessCommand,
        process: Popen[str],
    ) -> None:
        try:
            stdout, stderr = process.communicate(input=command.stdin)
            try:
                self._validate_captured_security(
                    task=task,
                    command=command,
                    stdout=stdout,
                    stderr=stderr,
                )
                result = self._result_or_error(
                    task=task,
                    command=command,
                    returncode=cast(int, process.returncode),
                    stdout=stdout,
                    stderr=stderr,
                )
            except ExecutorError as exc:
                completion = AttemptCompletion(handle=handle, error=exc)
            else:
                completion = AttemptCompletion(handle=handle, result=result)
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

    def _finish_handle(
        self,
        *,
        handle: ExecutionHandle,
        completion: AttemptCompletion,
    ) -> None:
        with self._lock:
            active = self._active.pop(handle.handle_id, None)
            self._completed_handle_ids.add(handle.handle_id)
        if active is not None:
            active.done_event.set()
        self._completion_queue.put(completion)

    def _validate_security(
        self,
        *,
        task: TaskDefinition,
        command: SubprocessCommand,
    ) -> None:
        try:
            self._security_policy.validate(command)
        except (TypeError, ValueError, UnicodeError) as exc:
            raise SubprocessSecurityError(
                task_id=task.task_id,
                handler_ref=task.handler_ref,
                violation=str(exc) or type(exc).__name__,
            ) from exc

    def _validate_captured_security(
        self,
        *,
        task: TaskDefinition,
        command: SubprocessCommand,
        stdout: str,
        stderr: str,
    ) -> None:
        try:
            self._security_policy.validate_captured_output(
                command=command,
                stdout=stdout,
                stderr=stderr,
            )
        except (TypeError, ValueError, UnicodeError) as exc:
            raise SubprocessSecurityError(
                task_id=task.task_id,
                handler_ref=task.handler_ref,
                violation=str(exc) or type(exc).__name__,
            ) from exc

    def _result_or_error(
        self,
        *,
        task: TaskDefinition,
        command: SubprocessCommand,
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> TaskResult:
        if returncode != 0:
            raise SubprocessExecutionError(
                task_id=task.task_id,
                handler_ref=task.handler_ref,
                argv=command.argv,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
            )

        result = SubprocessResult(
            argv=command.argv,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )
        return TaskResult(
            output=result,
            metadata={
                "returncode": returncode,
                "executable": command.argv[0],
            },
        )

    def _terminate_process(self, process: Popen[str]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=self._terminate_grace_seconds)
        except TimeoutExpired:
            process.kill()
            process.wait()


__all__ = [
    "SubprocessCommand",
    "SubprocessExecutor",
    "SubprocessResult",
    "SubprocessSecurityPolicy",
]
