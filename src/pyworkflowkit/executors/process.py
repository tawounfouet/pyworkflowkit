"""Canonical V2 isolated-process executor."""

from __future__ import annotations

import pickle  # nosec B403 - trusted intra-runtime process transport only
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import get_all_start_methods, get_context
from multiprocessing.connection import Connection
from multiprocessing.context import BaseContext
from multiprocessing.process import BaseProcess
from threading import RLock

from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
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
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId

_PROCESS_EXECUTOR_ID = "process"


@dataclass(frozen=True, slots=True)
class _ContextSnapshot:
    task_key: str
    workflow_run_id: str
    task_run_id: str
    attempt_id: str
    attempt_number: int
    correlation: CorrelationContext
    dependency_outputs: dict[str, object]
    workload_parameters: dict[str, str]


@dataclass(slots=True)
class _ActiveProcess:
    process: BaseProcess
    receive_connection: Connection
    cancellation_requested: bool = False


def _snapshot(request: TaskExecutionRequest, context: TaskExecutionContext) -> _ContextSnapshot:
    return _ContextSnapshot(
        task_key=request.task_key,
        workflow_run_id=str(context.workflow_run_id),
        task_run_id=str(context.task_run_id),
        attempt_id=str(context.attempt_id),
        attempt_number=context.attempt_number,
        correlation=context.correlation,
        dependency_outputs=dict(context.dependency_outputs),
        workload_parameters=dict(context.workload_parameters),
    )


def _restore_request(
    snapshot: _ContextSnapshot,
    handler: PythonHandler,
) -> TaskExecutionRequest:
    context = TaskExecutionContext(
        workflow_run_id=WorkflowRunId.parse(snapshot.workflow_run_id),
        task_run_id=TaskRunId.parse(snapshot.task_run_id),
        attempt_id=TaskAttemptId.parse(snapshot.attempt_id),
        attempt_number=snapshot.attempt_number,
        correlation=snapshot.correlation,
        dependency_outputs=snapshot.dependency_outputs,
        workload_parameters=snapshot.workload_parameters,
    )
    return TaskExecutionRequest(
        task_key=snapshot.task_key,
        workload=handler,
        executor_key=_PROCESS_EXECUTOR_ID,
        context=context,
    )


def _ensure_picklable(value: object) -> str | None:
    try:
        pickle.dumps(value)
    except Exception as exc:
        return f"{type(exc).__name__}: {str(exc) or type(exc).__name__}"
    return None


def _worker_main(
    send_connection: Connection,
    handler: PythonHandler,
    arity: int,
    snapshot: _ContextSnapshot,
) -> None:
    try:
        request = _restore_request(snapshot, handler)
        context = request.context
        try:
            raw = handler() if arity == 0 else handler(context)
        except Exception as exc:
            result = TaskExecutionResult(
                failure=FailureEvidence(
                    error_code=type(exc).__name__,
                    category=FailureCategory.INTERNAL,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    correlation_id=context.correlation.correlation_id,
                    workflow_run_id=str(context.workflow_run_id),
                    task_run_id=str(context.task_run_id),
                    task_attempt_id=str(context.attempt_id),
                    source_component="process_executor.worker",
                    message_summary=str(exc) or type(exc).__name__,
                )
            )
        else:
            result = (
                raw
                if isinstance(raw, TaskExecutionResult)
                else TaskExecutionResult(output=raw)
            )

        serialization_error = _ensure_picklable(result)
        if serialization_error is not None:
            result = TaskExecutionResult(
                failure=FailureEvidence(
                    error_code="PWK-PROCESS-RESULT-NONPORTABLE",
                    category=FailureCategory.CONTRACT_VIOLATION,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    correlation_id=context.correlation.correlation_id,
                    workflow_run_id=str(context.workflow_run_id),
                    task_run_id=str(context.task_run_id),
                    task_attempt_id=str(context.attempt_id),
                    source_component="process_executor.worker",
                    message_summary="process result cannot cross the serialization boundary",
                    details=(("serialization_error", serialization_error),),
                )
            )

        with suppress(BrokenPipeError, OSError):
            send_connection.send(result)
    finally:
        send_connection.close()


class ProcessExecutor:
    """Execute trusted Python handlers in dedicated, hard-terminable child processes."""

    def __init__(
        self,
        bindings: Mapping[str, PythonHandler] | None = None,
        *,
        max_workers: int = 2,
        start_method: str = "spawn",
        terminate_grace_seconds: float = 0.2,
    ) -> None:
        if isinstance(max_workers, bool) or not isinstance(max_workers, int):
            raise TypeError("max_workers must be an integer")
        if max_workers < 1:
            raise ValueError("max_workers must be greater than or equal to 1")
        if start_method not in get_all_start_methods():
            raise ValueError(f"unsupported multiprocessing start method: {start_method!r}")
        if isinstance(terminate_grace_seconds, bool) or not isinstance(
            terminate_grace_seconds,
            (int, float),
        ):
            raise TypeError("terminate_grace_seconds must be a number")
        if terminate_grace_seconds < 0:
            raise ValueError("terminate_grace_seconds must be greater than or equal to 0")

        self._bindings: dict[str, PythonHandler] = {}
        for key, handler in (bindings or {}).items():
            self.register(key, handler)

        self._max_workers = max_workers
        self._context: BaseContext = get_context(start_method)
        self._terminate_grace_seconds = float(terminate_grace_seconds)
        self._active: dict[TaskAttemptId, _ActiveProcess] = {}
        self._shutdown = False
        self._lock = RLock()
        self._descriptor = ExecutorDescriptor(
            executor_id=_PROCESS_EXECUTOR_ID,
            display_name="Process Executor",
            executor_version="1",
            capabilities=(
                "hard_cancellation",
                "hard_timeout",
                "process_isolation",
                "trusted_python",
            ),
            execution_modes=("child_process",),
            portability_constraints=(
                "handler_must_be_picklable",
                "inputs_must_be_picklable",
                "output_must_be_picklable",
                "trusted_python_not_security_sandbox",
            ),
            supported_workload_kinds=("python_callable", "registered"),
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
        if not isinstance(request, TaskExecutionRequest):
            raise TypeError("request must be a TaskExecutionRequest")
        if request.executor_key != self.descriptor.executor_id:
            return failure_result(
                request,
                error_code="PWK-EXECUTOR-MISMATCH",
                category=FailureCategory.CAPABILITY,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="process_executor",
                summary=(
                    f"request requires executor {request.executor_key!r}, "
                    f"but ProcessExecutor is {self.descriptor.executor_id!r}"
                ),
            )

        handler, parameters = resolve_handler(request, self._bindings)
        if handler is None:
            return failure_result(
                request,
                error_code="PWK-PROCESS-WORKLOAD-UNRESOLVED",
                category=FailureCategory.CAPABILITY,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="process_executor",
                summary="ProcessExecutor cannot resolve the declared workload",
            )

        try:
            arity = resolve_invocation_arity(handler)
        except (TypeError, ValueError) as exc:
            return failure_result(
                request,
                error_code="PWK-PROCESS-HANDLER-CONTRACT",
                category=FailureCategory.CONTRACT_VIOLATION,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="process_executor",
                summary=str(exc),
            )

        context = bound_context(request, parameters)
        snapshot = _snapshot(request, context)
        handler_error = _ensure_picklable(handler)
        snapshot_error = _ensure_picklable(snapshot)
        if handler_error is not None or snapshot_error is not None:
            detail_items: list[tuple[str, str]] = []
            if handler_error is not None:
                detail_items.append(("handler", handler_error))
            if snapshot_error is not None:
                detail_items.append(("context", snapshot_error))
            details = tuple(detail_items)
            return failure_result(
                request,
                error_code="PWK-PROCESS-SERIALIZATION",
                category=FailureCategory.CONTRACT_VIOLATION,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="process_executor",
                summary="process execution inputs cannot cross the serialization boundary",
                details=details,
            )

        remaining = _remaining_seconds(request)
        if remaining is not None and remaining <= 0:
            return _known_timeout(request, "execution deadline expired before process start")

        receive_connection, send_connection = self._context.Pipe(duplex=False)
        process = self._context.Process(
            target=_worker_main,
            args=(send_connection, handler, arity, snapshot),
            name=f"pyworkflowkit-v2-{context.attempt_id}",
        )

        with self._lock:
            if self._shutdown:
                receive_connection.close()
                send_connection.close()
                raise ExecutorShutdownError(executor_key=self.descriptor.executor_id)
            if len(self._active) >= self._max_workers:
                receive_connection.close()
                send_connection.close()
                return failure_result(
                    request,
                    error_code="PWK-PROCESS-CAPACITY",
                    category=FailureCategory.RESOURCE_EXHAUSTED,
                    retryability=Retryability.RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    source_component="process_executor",
                    summary="process executor capacity is saturated",
                )
            process.start()
            send_connection.close()
            self._active[context.attempt_id] = _ActiveProcess(
                process=process,
                receive_connection=receive_connection,
            )

        try:
            if remaining is None:
                try:
                    result = receive_connection.recv()
                except EOFError:
                    return self._process_exit_failure(request, process, context.attempt_id)
            else:
                if not receive_connection.poll(remaining):
                    self._terminate_process(process)
                    return _known_timeout(
                        request,
                        "child process exceeded its deadline and was terminated",
                    )
                try:
                    result = receive_connection.recv()
                except EOFError:
                    return self._process_exit_failure(request, process, context.attempt_id)

            if not isinstance(result, TaskExecutionResult):
                return failure_result(
                    request,
                    error_code="PWK-PROCESS-WORKER-CONTRACT",
                    category=FailureCategory.CONTRACT_VIOLATION,
                    retryability=Retryability.NON_RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    source_component="process_executor",
                    summary="child process returned an invalid execution result",
                )
            return result
        finally:
            receive_connection.close()
            process.join()
            with self._lock:
                self._active.pop(context.attempt_id, None)
            process.close()

    def cancel(self, request: TaskCancellationRequest) -> TaskCancellationResult:
        if not isinstance(request, TaskCancellationRequest):
            raise TypeError("request must be a TaskCancellationRequest")

        with self._lock:
            active = self._active.get(request.attempt_id)
            if active is None:
                return TaskCancellationResult(
                    status=CancellationStatus.UNCONFIRMED,
                    attempt_id=request.attempt_id,
                    reason="process_execution_handle_not_available",
                )
            if not active.process.is_alive():
                return TaskCancellationResult(
                    status=CancellationStatus.ALREADY_TERMINAL,
                    attempt_id=request.attempt_id,
                    reason="process_already_terminal",
                )
            active.cancellation_requested = True
            self._terminate_process(active.process)

        return TaskCancellationResult(
            status=CancellationStatus.CONFIRMED,
            attempt_id=request.attempt_id,
            reason="child_process_hard_terminated",
        )

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._shutdown = True
            active = tuple(self._active.values())

        if not wait:
            for execution in active:
                self._terminate_process(execution.process)
            return

        for execution in active:
            execution.process.join()

    def __enter__(self) -> ProcessExecutor:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.shutdown(wait=True)

    def _process_exit_failure(
        self,
        request: TaskExecutionRequest,
        process: BaseProcess,
        attempt_id: TaskAttemptId,
    ) -> TaskExecutionResult:
        with self._lock:
            active = self._active.get(attempt_id)
            cancelled = active is not None and active.cancellation_requested

        if cancelled:
            return failure_result(
                request,
                error_code="PWK-PROCESS-CANCELLED",
                category=FailureCategory.CANCELLED,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                source_component="process_executor",
                summary="child process was cancelled by the runtime",
            )

        return failure_result(
            request,
            error_code="PWK-PROCESS-EXITED-WITHOUT-RESULT",
            category=FailureCategory.INTERNAL,
            retryability=Retryability.NON_RETRYABLE,
            uncertainty=OutcomeUncertainty.KNOWN,
            source_component="process_executor",
            summary=f"child process exited without result; exitcode={process.exitcode}",
        )

    def _terminate_process(self, process: BaseProcess) -> None:
        if not process.is_alive():
            return
        process.terminate()
        process.join(timeout=self._terminate_grace_seconds)
        if process.is_alive():
            process.kill()
            process.join()


def _remaining_seconds(request: TaskExecutionRequest) -> float | None:
    if request.deadline_at is None:
        return None
    now = datetime.now(tz=request.deadline_at.tzinfo)
    return max(0.0, (request.deadline_at - now).total_seconds())


def _known_timeout(request: TaskExecutionRequest, summary: str) -> TaskExecutionResult:
    return failure_result(
        request,
        error_code="PWK-PROCESS-HARD-TIMEOUT",
        category=FailureCategory.TIMEOUT,
        retryability=Retryability.RETRYABLE,
        uncertainty=OutcomeUncertainty.KNOWN,
        source_component="process_executor",
        summary=summary,
    )


_protocol_probe = ProcessExecutor(max_workers=1)
try:
    if not isinstance(_protocol_probe, Executor):
        raise TypeError("ProcessExecutor must satisfy Executor")
    if not isinstance(_protocol_probe, CancellableExecutor):
        raise TypeError("ProcessExecutor must satisfy CancellableExecutor")
finally:
    _protocol_probe.shutdown()


__all__ = ["ProcessExecutor"]
