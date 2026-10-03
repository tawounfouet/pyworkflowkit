"""Canonical V2 shell-free subprocess executor."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen, TimeoutExpired  # nosec B404
from threading import RLock
from types import MappingProxyType

from pyworkflowkit.authoring.workloads import WorkloadPortability
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
    TaskExecutionRequest,
    TaskExecutionResult,
)
from pyworkflowkit.runtime.identity import TaskAttemptId

_SUBPROCESS_EXECUTOR_ID = "subprocess"


@dataclass(frozen=True, slots=True)
class SubprocessCommand:
    """Portable shell-free external command declaration."""

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
                    raise ValueError(
                        "env keys must be non-empty and contain neither '=' nor NUL"
                    )
                if "\x00" in value:
                    raise ValueError("env values must not contain NUL characters")
                copied_env[key] = value
            frozen_env = MappingProxyType(copied_env)

        object.__setattr__(self, "argv", argv)
        object.__setattr__(self, "env", frozen_env)

    @property
    def workload_kind(self) -> str:
        return "subprocess"

    @property
    def portability(self) -> WorkloadPortability:
        return WorkloadPortability.PORTABLE

    @property
    def executor_key(self) -> str:
        return _SUBPROCESS_EXECUTOR_ID

    def fingerprint_payload(self) -> Mapping[str, object]:
        return {
            "kind": self.workload_kind,
            "argv": list(self.argv),
            "cwd": self.cwd,
            "env": dict(self.env) if self.env is not None else None,
            "stdin": self.stdin,
            "encoding": self.encoding,
            "executor_key": self.executor_key,
            "contract_version": "1",
        }


@dataclass(frozen=True, slots=True)
class SubprocessResult:
    """Captured evidence from one external program invocation."""

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class SubprocessSecurityPolicy:
    """Guardrails for external command execution; not an operating-system sandbox."""

    allowed_executables: frozenset[str] | None = None
    allowed_cwd_roots: tuple[str, ...] = ()
    allowed_env_keys: frozenset[str] | None = None
    inherit_environment: bool = False
    max_stdin_bytes: int | None = 1_048_576
    max_stdout_bytes: int | None = 10_485_760
    max_stderr_bytes: int | None = 10_485_760

    def __post_init__(self) -> None:
        if not isinstance(self.inherit_environment, bool):
            raise TypeError("inherit_environment must be a bool")
        for field_name, value in (
            ("max_stdin_bytes", self.max_stdin_bytes),
            ("max_stdout_bytes", self.max_stdout_bytes),
            ("max_stderr_bytes", self.max_stderr_bytes),
        ):
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise TypeError(f"{field_name} must be an integer or None")
                if value < 0:
                    raise ValueError(f"{field_name} must be greater than or equal to 0")

        roots = tuple(str(Path(root).resolve()) for root in self.allowed_cwd_roots)
        object.__setattr__(self, "allowed_cwd_roots", roots)
        if self.allowed_executables is not None:
            object.__setattr__(
                self,
                "allowed_executables",
                frozenset(self.allowed_executables),
            )
        if self.allowed_env_keys is not None:
            object.__setattr__(
                self,
                "allowed_env_keys",
                frozenset(self.allowed_env_keys),
            )

    def validate(self, command: SubprocessCommand) -> None:
        executable = command.argv[0]
        if self.allowed_executables is not None and executable not in self.allowed_executables:
            raise ValueError("executable is not allowed by subprocess security policy")

        if command.cwd is not None and self.allowed_cwd_roots:
            cwd = Path(command.cwd).resolve()
            allowed = any(
                cwd == Path(root) or cwd.is_relative_to(Path(root))
                for root in self.allowed_cwd_roots
            )
            if not allowed:
                raise ValueError("cwd is outside allowed subprocess roots")

        if command.env is not None and self.allowed_env_keys is not None:
            disallowed = sorted(set(command.env) - set(self.allowed_env_keys))
            if disallowed:
                raise ValueError("explicit environment contains disallowed keys")

        if command.stdin is not None:
            self._validate_size(
                "stdin",
                len(command.stdin.encode(command.encoding)),
                self.max_stdin_bytes,
            )

    def environment_for(self, command: SubprocessCommand) -> dict[str, str]:
        if command.env is not None:
            environment = dict(command.env)
        elif self.inherit_environment:
            environment = dict(os.environ)
        else:
            environment = {}

        if self.allowed_env_keys is not None:
            environment = {
                key: value for key, value in environment.items() if key in self.allowed_env_keys
            }
        return environment

    def validate_captured_output(
        self,
        *,
        command: SubprocessCommand,
        stdout: str,
        stderr: str,
    ) -> None:
        self._validate_size(
            "stdout",
            len(stdout.encode(command.encoding, errors="replace")),
            self.max_stdout_bytes,
        )
        self._validate_size(
            "stderr",
            len(stderr.encode(command.encoding, errors="replace")),
            self.max_stderr_bytes,
        )

    @staticmethod
    def _validate_size(label: str, actual: int, maximum: int | None) -> None:
        if maximum is not None and actual > maximum:
            raise ValueError(f"{label} exceeds subprocess security policy limit")


@dataclass(slots=True)
class _ActiveSubprocess:
    process: Popen[str]
    cancellation_requested: bool = False


class SubprocessExecutor:
    """Execute external argv-based programs with shell disabled."""

    def __init__(
        self,
        bindings: Mapping[str, PythonHandler] | None = None,
        *,
        max_workers: int = 4,
        terminate_grace_seconds: float = 0.2,
        security_policy: SubprocessSecurityPolicy | None = None,
    ) -> None:
        if isinstance(max_workers, bool) or not isinstance(max_workers, int):
            raise TypeError("max_workers must be an integer")
        if max_workers < 1:
            raise ValueError("max_workers must be greater than or equal to 1")
        if isinstance(terminate_grace_seconds, bool) or not isinstance(
            terminate_grace_seconds,
            (int, float),
        ):
            raise TypeError("terminate_grace_seconds must be a number")
        if terminate_grace_seconds < 0:
            raise ValueError("terminate_grace_seconds must be greater than or equal to 0")
        if security_policy is not None and not isinstance(
            security_policy,
            SubprocessSecurityPolicy,
        ):
            raise TypeError("security_policy must be a SubprocessSecurityPolicy or None")

        self._bindings: dict[str, PythonHandler] = {}
        for key, handler in (bindings or {}).items():
            self.register(key, handler)

        self._max_workers = max_workers
        self._terminate_grace_seconds = float(terminate_grace_seconds)
        self._security_policy = security_policy or SubprocessSecurityPolicy()
        self._active: dict[TaskAttemptId, _ActiveSubprocess] = {}
        self._completed: set[TaskAttemptId] = set()
        self._shutdown = False
        self._lock = RLock()
        self._descriptor = ExecutorDescriptor(
            executor_id=_SUBPROCESS_EXECUTOR_ID,
            display_name="Subprocess Executor",
            executor_version="1",
            capabilities=(
                "captured_output",
                "hard_cancellation",
                "hard_timeout",
                "shell_free_argv",
            ),
            execution_modes=("external_process",),
            portability_constraints=(
                "not_security_sandbox",
                "operating_system_program_required",
                "shell_disabled",
            ),
            supported_workload_kinds=("python_callable", "registered", "subprocess"),
            performs_implicit_workload_retry=False,
            supports_execution_timeout=True,
            cancellation_capability=CancellationCapability.CONFIRMED,
        )

    @property
    def descriptor(self) -> ExecutorDescriptor:
        return self._descriptor

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def security_policy(self) -> SubprocessSecurityPolicy:
        return self._security_policy

    def register(self, key: str, handler: PythonHandler) -> None:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("registered workload key must not be empty")
        if not callable(handler):
            raise TypeError("registered workload handler must be callable")
        if key in self._bindings:
            raise ValueError(f"registered workload {key!r} already exists")
        self._bindings[key] = handler

    def execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        if not isinstance(request, TaskExecutionRequest):
            raise TypeError("request must be a TaskExecutionRequest")
        if request.executor_key != self.descriptor.executor_id:
            return failure_result(
                request,
                error_code="PWK-EXECUTOR-MISMATCH",
                category=FailureCategory.CAPABILITY,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="subprocess_executor",
                summary=(
                    f"request requires executor {request.executor_key!r}, "
                    f"but SubprocessExecutor is {self.descriptor.executor_id!r}"
                ),
            )

        command_or_failure = self._resolve_command(request)
        if isinstance(command_or_failure, TaskExecutionResult):
            return command_or_failure
        command = command_or_failure

        try:
            self._security_policy.validate(command)
        except ValueError as exc:
            return failure_result(
                request,
                error_code="PWK-SUBPROCESS-SECURITY",
                category=FailureCategory.VALIDATION,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="subprocess_executor",
                summary=str(exc),
            )

        remaining = _remaining_seconds(request)
        if remaining is not None and remaining <= 0:
            return _known_timeout(request, "execution deadline expired before subprocess spawn")

        with self._lock:
            if self._shutdown:
                raise ExecutorShutdownError(executor_key=self.descriptor.executor_id)
            if len(self._active) >= self._max_workers:
                return failure_result(
                    request,
                    error_code="PWK-SUBPROCESS-CAPACITY",
                    category=FailureCategory.RESOURCE_EXHAUSTED,
                    retryability=Retryability.RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    source_component="subprocess_executor",
                    summary="subprocess executor capacity is saturated",
                )

        try:
            process = Popen(  # nosec B603 - validated argv with shell=False
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
        except FileNotFoundError as exc:
            return failure_result(
                request,
                error_code="PWK-SUBPROCESS-NOT-FOUND",
                category=FailureCategory.NOT_FOUND,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="subprocess_executor",
                summary=str(exc) or "subprocess executable was not found",
            )
        except OSError as exc:
            return failure_result(
                request,
                error_code=type(exc).__name__,
                category=FailureCategory.INTERNAL,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="subprocess_executor",
                summary=str(exc) or type(exc).__name__,
            )

        attempt_id = request.context.attempt_id
        with self._lock:
            self._active[attempt_id] = _ActiveSubprocess(process=process)

        try:
            try:
                stdout, stderr = process.communicate(
                    input=command.stdin,
                    timeout=remaining,
                )
            except TimeoutExpired:
                self._terminate_process(process)
                stdout, stderr = process.communicate()
                return _known_timeout(
                    request,
                    "subprocess exceeded its deadline and was hard terminated",
                    stdout=stdout,
                    stderr=stderr,
                )

            with self._lock:
                active = self._active.get(attempt_id)
                cancelled = active is not None and active.cancellation_requested
            if cancelled:
                return failure_result(
                    request,
                    error_code="PWK-SUBPROCESS-CANCELLED",
                    category=FailureCategory.CANCELLED,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    source_component="subprocess_executor",
                    summary="subprocess was cancelled by the runtime",
                )

            try:
                self._security_policy.validate_captured_output(
                    command=command,
                    stdout=stdout,
                    stderr=stderr,
                )
            except ValueError as exc:
                return failure_result(
                    request,
                    error_code="PWK-SUBPROCESS-OUTPUT-POLICY",
                    category=FailureCategory.VALIDATION,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    source_component="subprocess_executor",
                    summary=str(exc),
                )

            returncode = process.returncode
            if returncode is None:
                return failure_result(
                    request,
                    error_code="PWK-SUBPROCESS-MISSING-RETURNCODE",
                    category=FailureCategory.INTERNAL,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    source_component="subprocess_executor",
                    summary="subprocess completed without a return code",
                )
            if returncode != 0:
                return failure_result(
                    request,
                    error_code="PWK-SUBPROCESS-NONZERO-EXIT",
                    category=FailureCategory.EXTERNAL_PROVIDER,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    source_component="subprocess_executor",
                    summary=f"subprocess exited with return code {returncode}",
                    details=(
                        ("returncode", str(returncode)),
                        ("stderr", stderr[-2048:]),
                    ),
                )

            return TaskExecutionResult(
                output=SubprocessResult(
                    argv=command.argv,
                    returncode=returncode,
                    stdout=stdout,
                    stderr=stderr,
                )
            )
        finally:
            with self._lock:
                self._active.pop(attempt_id, None)
                self._completed.add(attempt_id)

    def cancel(self, request: TaskCancellationRequest) -> TaskCancellationResult:
        if not isinstance(request, TaskCancellationRequest):
            raise TypeError("request must be a TaskCancellationRequest")

        with self._lock:
            active = self._active.get(request.attempt_id)
            if active is None:
                status = (
                    CancellationStatus.ALREADY_TERMINAL
                    if request.attempt_id in self._completed
                    else CancellationStatus.UNCONFIRMED
                )
                reason = (
                    "subprocess_already_terminal"
                    if status is CancellationStatus.ALREADY_TERMINAL
                    else "subprocess_execution_handle_not_available"
                )
                return TaskCancellationResult(
                    status=status,
                    attempt_id=request.attempt_id,
                    reason=reason,
                )
            if active.process.poll() is not None:
                return TaskCancellationResult(
                    status=CancellationStatus.ALREADY_TERMINAL,
                    attempt_id=request.attempt_id,
                    reason="subprocess_already_terminal",
                )
            active.cancellation_requested = True
            self._terminate_process(active.process)

        return TaskCancellationResult(
            status=CancellationStatus.CONFIRMED,
            attempt_id=request.attempt_id,
            reason="subprocess_hard_terminated",
        )

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._shutdown = True
            active = tuple(self._active.values())

        if wait:
            for execution in active:
                execution.process.wait()
            return

        for execution in active:
            self._terminate_process(execution.process)

    def __enter__(self) -> SubprocessExecutor:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.shutdown(wait=True)

    def _resolve_command(
        self,
        request: TaskExecutionRequest,
    ) -> SubprocessCommand | TaskExecutionResult:
        if isinstance(request.workload, SubprocessCommand):
            return request.workload

        handler, parameters = resolve_handler(request, self._bindings)
        if handler is None:
            return failure_result(
                request,
                error_code="PWK-SUBPROCESS-WORKLOAD-UNRESOLVED",
                category=FailureCategory.CAPABILITY,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="subprocess_executor",
                summary="SubprocessExecutor cannot resolve the declared workload",
            )
        try:
            arity = resolve_invocation_arity(handler)
        except (TypeError, ValueError) as exc:
            return failure_result(
                request,
                error_code="PWK-SUBPROCESS-HANDLER-CONTRACT",
                category=FailureCategory.CONTRACT_VIOLATION,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="subprocess_executor",
                summary=str(exc),
            )

        context = bound_context(request, parameters)
        try:
            raw = handler() if arity == 0 else handler(context)
        except Exception as exc:
            return failure_result(
                request,
                error_code=type(exc).__name__,
                category=FailureCategory.INTERNAL,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="subprocess_executor",
                summary=str(exc) or type(exc).__name__,
            )
        if not isinstance(raw, SubprocessCommand):
            return failure_result(
                request,
                error_code="PWK-SUBPROCESS-COMMAND-CONTRACT",
                category=FailureCategory.CONTRACT_VIOLATION,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="subprocess_executor",
                summary="SubprocessExecutor handler must return SubprocessCommand",
            )
        return raw

    def _terminate_process(self, process: Popen[str]) -> None:
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=self._terminate_grace_seconds)
        except TimeoutExpired:
            process.kill()
            process.wait()


def _remaining_seconds(request: TaskExecutionRequest) -> float | None:
    if request.deadline_at is None:
        return None
    now = datetime.now(tz=request.deadline_at.tzinfo)
    return max(0.0, (request.deadline_at - now).total_seconds())


def _known_timeout(
    request: TaskExecutionRequest,
    summary: str,
    *,
    stdout: str = "",
    stderr: str = "",
) -> TaskExecutionResult:
    details: tuple[tuple[str, str], ...] = ()
    if stdout or stderr:
        details = (
            ("stdout", stdout[-2048:]),
            ("stderr", stderr[-2048:]),
        )
    return failure_result(
        request,
        error_code="PWK-SUBPROCESS-HARD-TIMEOUT",
        category=FailureCategory.TIMEOUT,
        retryability=Retryability.RETRYABLE,
        uncertainty=OutcomeUncertainty.KNOWN,
        source_component="subprocess_executor",
        summary=summary,
        details=details,
    )


_protocol_probe = SubprocessExecutor(max_workers=1)
try:
    if not isinstance(_protocol_probe, Executor):
        raise TypeError("SubprocessExecutor must satisfy Executor")
    if not isinstance(_protocol_probe, CancellableExecutor):
        raise TypeError("SubprocessExecutor must satisfy CancellableExecutor")
finally:
    _protocol_probe.shutdown()


__all__ = [
    "SubprocessCommand",
    "SubprocessExecutor",
    "SubprocessResult",
    "SubprocessSecurityPolicy",
]
