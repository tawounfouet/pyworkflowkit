"""Shared internals for canonical V2 executor adapters."""

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
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
)

PythonHandler = Callable[..., object]


def resolve_handler(
    request: TaskExecutionRequest,
    bindings: Mapping[str, PythonHandler],
) -> tuple[PythonHandler | None, Mapping[str, str]]:
    workload = request.workload
    if isinstance(workload, RegisteredWorkload):
        return bindings.get(workload.registry_key), dict(workload.parameters)
    if callable(workload):
        return workload, {}
    return None, {}


def resolve_invocation_arity(handler: PythonHandler) -> int:
    try:
        handler_signature = signature(handler)
    except (TypeError, ValueError) as exc:
        raise ValueError("handler signature cannot be inspected") from exc

    if _can_bind(handler_signature):
        return 0
    if _can_bind(handler_signature, object()):
        return 1
    raise ValueError("handler must accept zero arguments or one TaskExecutionContext argument")


def invoke_handler(
    handler: PythonHandler,
    *,
    arity: int,
    context: TaskExecutionContext,
    request: TaskExecutionRequest,
    source_component: str,
) -> TaskExecutionResult:
    try:
        raw = handler() if arity == 0 else handler(context)
    except Exception as exc:
        return failure_result(
            request,
            error_code=type(exc).__name__,
            category=FailureCategory.INTERNAL,
            retryability=Retryability.NON_RETRYABLE,
            uncertainty=OutcomeUncertainty.KNOWN,
            source_component=source_component,
            summary=str(exc) or type(exc).__name__,
        )
    if isinstance(raw, TaskExecutionResult):
        return raw
    return TaskExecutionResult(output=raw)


def failure_result(
    request: TaskExecutionRequest,
    *,
    error_code: str,
    category: FailureCategory,
    retryability: Retryability,
    uncertainty: OutcomeUncertainty,
    source_component: str,
    summary: str,
    details: tuple[tuple[str, str], ...] = (),
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
            source_component=source_component,
            message_summary=summary,
            details=details,
        )
    )


def bound_context(
    request: TaskExecutionRequest,
    parameters: Mapping[str, str],
) -> TaskExecutionContext:
    return TaskExecutionContext(
        workflow_run_id=request.context.workflow_run_id,
        task_run_id=request.context.task_run_id,
        attempt_id=request.context.attempt_id,
        attempt_number=request.context.attempt_number,
        correlation=request.context.correlation,
        dependency_outputs=request.context.dependency_outputs,
        workload_parameters=parameters,
    )


def _can_bind(handler_signature: Signature, *args: object) -> bool:
    try:
        handler_signature.bind(*args)
    except TypeError:
        return False
    return all(
        parameter.kind not in {Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD}
        for parameter in handler_signature.parameters.values()
    )


__all__ = [
    "PythonHandler",
    "bound_context",
    "failure_result",
    "invoke_handler",
    "resolve_handler",
    "resolve_invocation_arity",
]
