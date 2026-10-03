"""Trusted bounded worker-thread executor for the V2 execution contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime
from inspect import Parameter, Signature, signature
from threading import RLock

from pyworkflowkit.authoring.workloads import RegisteredWorkload
from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.errors import ExecutorShutdownError
from pyworkflowkit.executors.contracts import (
    CancellationCapability,
    Executor,
    ExecutorDescriptor,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
)

ThreadHandler = Callable[..., object]


class ThreadExecutor:
    """Execute trusted Python callables in a bounded same-process thread pool.

    Execution through WorkflowRuntime remains synchronously coordinated. The worker-thread
    boundary is useful for bounded thread isolation and soft deadline observation, but it
    does not make the V2 WorkflowRuntime itself a concurrent DAG scheduler.
    """

    _EXECUTOR_ID = "thread"

    def __init__(
        self,
        bindings: Mapping[str, ThreadHandler] | None = None,
        *,
        max_workers: int = 4,
        thread_name_prefix: str = "pyworkflowkit-v2",
    ) -> None:
        if isinstance(max_workers, bool) or not isinstance(max_workers, int):
            raise TypeError("max_workers must be an integer")
        if max_workers < 1:
            raise ValueError("max_workers must be greater than or equal to 1")
        if not isinstance(thread_name_prefix, str) or not thread_name_prefix.strip():
            raise ValueError("thread_name_prefix must not be blank")

        self._bindings: dict[str, ThreadHandler] = {}
        for key, handler in (bindings or {}).items():
            self.register(key, handler)

        self._max_workers = max_workers
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        self._shutdown = False
        self._lock = RLock()
        self._descriptor = ExecutorDescriptor(
            executor_id=self._EXECUTOR_ID,
            display_name="Thread Executor",
            executor_version="1",
            capabilities=(
                "bounded_thread_pool",
                "synchronous_bridge",
                "trusted_python",
            ),
            execution_modes=("worker_thread",),
            portability_constraints=(
                "deadline_does_not_stop_running_thread",
                "same_process",
                "shared_memory",
            ),
            supported_workload_kinds=("python_callable", "registered"),
            performs_implicit_workload_retry=False,
            supports_execution_timeout=True,
            cancellation_capability=CancellationCapability.UNSUPPORTED,
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

    def register(self, key: str, handler: ThreadHandler) -> None:
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
            return _failure_result(
                request,
                error_code="PWK-EXECUTOR-MISMATCH",
                category=FailureCategory.CAPABILITY,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                summary=(
                    f"request requires executor {request.executor_key!r}, "
                    f"but ThreadExecutor is {self.descriptor.executor_id!r}"
                ),
            )

        with self._lock:
            if self._shutdown:
                raise ExecutorShutdownError(executor_key=self.descriptor.executor_id)

        handler, parameters = self._resolve(request)
        if handler is None:
            return _failure_result(
                request,
                error_code="PWK-THREAD-WORKLOAD-UNRESOLVED",
                category=FailureCategory.CAPABILITY,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                summary="ThreadExecutor cannot resolve the declared workload",
            )

        context = TaskExecutionContext(
            workflow_run_id=request.context.workflow_run_id,
            task_run_id=request.context.task_run_id,
            attempt_id=request.context.attempt_id,
            attempt_number=request.context.attempt_number,
            correlation=request.context.correlation,
            dependency_outputs=request.context.dependency_outputs,
            workload_parameters=parameters,
        )

        try:
            arity = _resolve_invocation_arity(handler)
        except (TypeError, ValueError) as exc:
            return _failure_result(
                request,
                error_code="PWK-THREAD-HANDLER-CONTRACT",
                category=FailureCategory.CONTRACT_VIOLATION,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                summary=str(exc),
            )

        remaining: float | None = None
        if request.deadline_at is not None:
            remaining = _remaining_seconds(request.deadline_at)
            if remaining <= 0:
                return _known_timeout_result(request)

        with self._lock:
            if self._shutdown:
                raise ExecutorShutdownError(executor_key=self.descriptor.executor_id)
            future = self._pool.submit(_invoke, handler, context, arity, request)

        if remaining is None:
            return future.result()

        try:
            return future.result(timeout=remaining)
        except FutureTimeoutError:
            if future.cancel():
                return _known_timeout_result(request)
            return _soft_timeout_result(request)

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            self._shutdown = True
        self._pool.shutdown(wait=wait, cancel_futures=False)

    def __enter__(self) -> ThreadExecutor:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.shutdown(wait=True)

    def _resolve(
        self,
        request: TaskExecutionRequest,
    ) -> tuple[ThreadHandler | None, Mapping[str, str]]:
        workload = request.workload
        if isinstance(workload, RegisteredWorkload):
            return self._bindings.get(workload.registry_key), dict(workload.parameters)
        if callable(workload):
            return workload, {}
        return None, {}


def _invoke(
    handler: ThreadHandler,
    context: TaskExecutionContext,
    arity: int,
    request: TaskExecutionRequest,
) -> TaskExecutionResult:
    try:
        raw = handler() if arity == 0 else handler(context)
    except Exception as exc:
        return _failure_result(
            request,
            error_code=type(exc).__name__,
            category=FailureCategory.INTERNAL,
            retryability=Retryability.NON_RETRYABLE,
            uncertainty=OutcomeUncertainty.KNOWN,
            summary=str(exc) or type(exc).__name__,
        )
    if isinstance(raw, TaskExecutionResult):
        return raw
    return TaskExecutionResult(output=raw)


def _remaining_seconds(deadline_at: datetime) -> float:
    now = datetime.now(tz=deadline_at.tzinfo)
    return (deadline_at - now).total_seconds()


def _known_timeout_result(request: TaskExecutionRequest) -> TaskExecutionResult:
    return _failure_result(
        request,
        error_code="PWK-THREAD-DEADLINE-EXPIRED",
        category=FailureCategory.TIMEOUT,
        retryability=Retryability.RETRYABLE,
        uncertainty=OutcomeUncertainty.KNOWN,
        summary="thread execution deadline expired before work could continue",
    )


def _soft_timeout_result(request: TaskExecutionRequest) -> TaskExecutionResult:
    return _failure_result(
        request,
        error_code="PWK-THREAD-SOFT-TIMEOUT",
        category=FailureCategory.TIMEOUT,
        retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
        uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
        summary="thread execution exceeded its deadline and may still be running",
    )


def _resolve_invocation_arity(handler: ThreadHandler) -> int:
    try:
        handler_signature = signature(handler)
    except (TypeError, ValueError) as exc:
        raise ValueError("handler signature cannot be inspected") from exc

    if _can_bind(handler_signature):
        return 0
    if _can_bind(handler_signature, object()):
        return 1
    raise ValueError("handler must accept zero arguments or one TaskExecutionContext argument")


def _can_bind(handler_signature: Signature, *args: object) -> bool:
    try:
        handler_signature.bind(*args)
    except TypeError:
        return False
    return all(
        parameter.kind not in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}
        for parameter in handler_signature.parameters.values()
    )


def _failure_result(
    request: TaskExecutionRequest,
    *,
    error_code: str,
    category: FailureCategory,
    retryability: Retryability,
    uncertainty: OutcomeUncertainty,
    summary: str,
) -> TaskExecutionResult:
    return TaskExecutionResult(
        failure=FailureEvidence(
            error_code=error_code,
            category=category,
            retryability=retryability,
            uncertainty=uncertainty,
            correlation_id=request.context.correlation.correlation_id,
            workflow_run_id=str(request.context.workflow_run_id),
            task_run_id=str(request.context.task_run_id),
            task_attempt_id=str(request.context.attempt_id),
            source_component="thread_executor",
            message_summary=summary,
        )
    )


_protocol_probe = ThreadExecutor(max_workers=1)
try:
    if not isinstance(_protocol_probe, Executor):
        raise TypeError("ThreadExecutor must satisfy Executor")
finally:
    _protocol_probe.shutdown()


__all__ = ["ThreadExecutor"]
