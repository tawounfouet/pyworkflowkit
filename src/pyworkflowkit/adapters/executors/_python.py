"""Shared trusted-Python handler invocation mechanics for in-process executors."""

from __future__ import annotations

import logging
from inspect import Parameter, Signature, signature
from typing import cast

from pyworkflowkit.application.observability import LogContext, log_runtime
from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.values import TaskResult
from pyworkflowkit.errors import InvalidHandlerError, TaskExecutionError
from pyworkflowkit.ports.executor import (
    ContextHandler,
    RunContext,
    TaskHandler,
    ZeroArgumentHandler,
)


def invoke_python_handler(
    *,
    task: TaskDefinition,
    handler: TaskHandler,
    context: RunContext,
    executor_key: str,
    logger: logging.Logger,
) -> TaskResult:
    """Invoke one trusted Python handler using the common executor contract."""

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
    log_runtime(logger, logging.DEBUG, "Executor invocation started", context=log_context)

    try:
        if invocation_arity == 0:
            raw_result = cast(ZeroArgumentHandler, handler)()
        else:
            raw_result = cast(ContextHandler, handler)(context)
    except Exception as exc:
        log_runtime(
            logger,
            logging.WARNING,
            "Executor invocation failed",
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
    log_runtime(logger, logging.DEBUG, "Executor invocation succeeded", context=log_context)
    return result


def resolve_invocation_arity(*, task: TaskDefinition, handler: TaskHandler) -> int:
    try:
        handler_signature = signature(handler)
    except (TypeError, ValueError) as exc:
        raise InvalidHandlerError(
            task_id=task.task_id,
            reason="handler signature cannot be inspected",
        ) from exc

    if _can_bind(handler_signature):
        return 0
    if _can_bind(handler_signature, object()):
        return 1

    raise InvalidHandlerError(
        task_id=task.task_id,
        reason="handler must accept either zero arguments or one RunContext argument",
    )


def normalize_result(raw_result: object) -> TaskResult:
    if isinstance(raw_result, TaskResult):
        return raw_result
    if raw_result is None:
        return TaskResult()
    return TaskResult(output=raw_result)


def _can_bind(handler_signature: Signature, *args: object) -> bool:
    try:
        handler_signature.bind(*args)
    except TypeError:
        return False

    for parameter in handler_signature.parameters.values():
        if parameter.kind is Parameter.VAR_POSITIONAL:
            return False
        if parameter.kind is Parameter.VAR_KEYWORD:
            return False
    return True


__all__ = ["invoke_python_handler", "normalize_result", "resolve_invocation_arity"]
