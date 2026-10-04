"""Trusted same-process V2 InlineExecutor."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from inspect import Parameter, Signature, signature

from pyworkflowkit.authoring.workloads import RegisteredWorkload
from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.executors.contracts import (
    CancellationCapability,
    Executor,
    ExecutorDescriptor,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from pyworkflowkit.runtime.telemetry import get_telemetry_bridge

LocalHandler = Callable[..., object]


class InlineExecutor:
    """Execute trusted Python callables synchronously in the current process."""

    _DESCRIPTOR = ExecutorDescriptor(
        executor_id="inline",
        display_name="Inline Executor",
        executor_version="1",
        capabilities=("synchronous", "trusted_python"),
        execution_modes=("current_process",),
        portability_constraints=("process_local_execution",),
        supported_workload_kinds=("python_callable", "registered"),
        supports_execution_timeout=False,
        cancellation_capability=CancellationCapability.UNSUPPORTED,
    )

    def __init__(self, bindings: Mapping[str, LocalHandler] | None = None) -> None:
        self._bindings: dict[str, LocalHandler] = {}
        for key, handler in (bindings or {}).items():
            self.register(key, handler)

    @property
    def descriptor(self) -> ExecutorDescriptor:
        return self._DESCRIPTOR

    def register(self, key: str, handler: LocalHandler) -> None:
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
                summary=(
                    f"request requires executor {request.executor_key!r}, "
                    f"but InlineExecutor is {self.descriptor.executor_id!r}"
                ),
            )

        handler, parameters = self._resolve(request)
        if handler is None:
            return _failure_result(
                request,
                error_code="PWK-INLINE-WORKLOAD-UNRESOLVED",
                category=FailureCategory.CAPABILITY,
                summary="InlineExecutor cannot resolve the declared workload",
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
                error_code="PWK-INLINE-HANDLER-CONTRACT",
                category=FailureCategory.CONTRACT_VIOLATION,
                summary=str(exc),
            )

        try:
            raw = handler() if arity == 0 else handler(context)
        except Exception as exc:
            get_telemetry_bridge().record_exception(exc)
            return _failure_result(
                request,
                error_code=type(exc).__name__,
                category=FailureCategory.INTERNAL,
                summary=str(exc) or type(exc).__name__,
            )

        if isinstance(raw, TaskExecutionResult):
            return raw
        return TaskExecutionResult(output=raw)

    def _resolve(
        self,
        request: TaskExecutionRequest,
    ) -> tuple[LocalHandler | None, Mapping[str, str]]:
        workload = request.workload
        if isinstance(workload, RegisteredWorkload):
            return self._bindings.get(workload.registry_key), dict(workload.parameters)
        if callable(workload):
            return workload, {}
        return None, {}


def _resolve_invocation_arity(handler: LocalHandler) -> int:
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
    summary: str,
) -> TaskExecutionResult:
    return TaskExecutionResult(
        failure=FailureEvidence(
            error_code=error_code,
            category=category,
            retryability=Retryability.NON_RETRYABLE,
            uncertainty=OutcomeUncertainty.KNOWN,
            correlation_id=request.context.correlation.correlation_id,
            workflow_run_id=str(request.context.workflow_run_id),
            task_run_id=str(request.context.task_run_id),
            task_attempt_id=str(request.context.attempt_id),
            source_component="inline_executor",
            message_summary=summary,
        )
    )


if not isinstance(InlineExecutor(), Executor):
    raise TypeError("InlineExecutor must satisfy Executor")


__all__ = ["InlineExecutor"]
