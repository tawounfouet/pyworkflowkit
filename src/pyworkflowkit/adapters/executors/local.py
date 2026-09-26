"""Synchronous same-process LocalExecutor."""

import logging
from inspect import Parameter, Signature, signature
from typing import cast

from pyworkflowkit.application.observability import LogContext, log_runtime
from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.values import TaskResult
from pyworkflowkit.errors import InvalidHandlerError, TaskExecutionError
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    ContextHandler,
    ExecutorCapabilities,
    RunContext,
    TaskHandler,
    TimeoutCapability,
    ZeroArgumentHandler,
)

logger = logging.getLogger("pyworkflowkit.executor.local")


class LocalExecutor:
    """Execute trusted Python handlers synchronously in the current process."""

    _CAPABILITIES = ExecutorCapabilities(
        supports_parallelism=False,
        timeout=TimeoutCapability.NONE,
        cancellation=CancellationCapability.NONE,
        max_concurrency=1,
    )

    @property
    def key(self) -> str:
        return "local"

    @property
    def capabilities(self) -> ExecutorCapabilities:
        return self._CAPABILITIES

    def execute(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> TaskResult:
        if task.executor_key != self.key:
            raise InvalidHandlerError(
                task_id=task.task_id,
                reason=(
                    f"task requests executor '{task.executor_key}', "
                    f"but LocalExecutor key is '{self.key}'"
                ),
            )

        invocation_arity = self._resolve_invocation_arity(
            task=task,
            handler=handler,
        )
        log_context = LogContext(
            run_id=str(context.workflow_run_id),
            task_run_id=str(context.task_run_id),
            task_id=str(context.task_id),
            attempt_number=context.attempt_number,
            executor_key=self.key,
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

        result = self._normalize_result(raw_result)
        log_runtime(logger, logging.DEBUG, "Executor invocation succeeded", context=log_context)
        return result

    @staticmethod
    def _resolve_invocation_arity(
        *,
        task: TaskDefinition,
        handler: TaskHandler,
    ) -> int:
        try:
            handler_signature = signature(handler)
        except (TypeError, ValueError) as exc:
            raise InvalidHandlerError(
                task_id=task.task_id,
                reason="handler signature cannot be inspected",
            ) from exc

        if LocalExecutor._can_bind(handler_signature):
            return 0
        if LocalExecutor._can_bind(handler_signature, object()):
            return 1

        raise InvalidHandlerError(
            task_id=task.task_id,
            reason="handler must accept either zero arguments or one RunContext argument",
        )

    @staticmethod
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

    @staticmethod
    def _normalize_result(raw_result: object) -> TaskResult:
        if isinstance(raw_result, TaskResult):
            return raw_result
        if raw_result is None:
            return TaskResult()
        return TaskResult(output=raw_result)


__all__ = ["LocalExecutor"]
