"""Lazy declarative workflow-definition helpers."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import ParamSpec, TypeVar, overload

from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import FailurePolicy
from pyworkflowkit.domain.ids import TaskId, WorkflowId
from pyworkflowkit.domain.values import RetryPolicy, WorkflowParameter
from pyworkflowkit.ports.executor import TaskHandler

P = ParamSpec("P")
R = TypeVar("R")

WorkflowDeclaration = Callable[[], Sequence["TaskHandle"]]


@dataclass(frozen=True, slots=True)
class TaskHandle:
    """Declarative task metadata paired with its Python handler."""

    task_id: TaskId
    handler_ref: str
    handler: TaskHandler
    depends_on: tuple[TaskId, ...] = ()
    retry_policy: RetryPolicy = RetryPolicy()
    executor_key: str = "local"
    timeout_seconds: float | None = None
    tags: frozenset[str] = frozenset()
    description: str | None = None

    def to_definition(self) -> TaskDefinition:
        """Materialize the immutable domain TaskDefinition."""

        return TaskDefinition(
            task_id=self.task_id,
            handler_ref=self.handler_ref,
            depends_on=self.depends_on,
            retry_policy=self.retry_policy,
            executor_key=self.executor_key,
            timeout_seconds=self.timeout_seconds,
            tags=self.tags,
            description=self.description,
        )


class WorkflowBuilder:
    """Lazy wrapper around a workflow declaration function.

    Building evaluates only the declaration function. Task handlers are never
    invoked by decoration or definition materialization.
    """

    def __init__(
        self,
        *,
        workflow_id: WorkflowId,
        version: str,
        declaration: WorkflowDeclaration,
        parameters: tuple[WorkflowParameter, ...] = (),
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
        description: str | None = None,
    ) -> None:
        self.workflow_id = workflow_id
        self.version = version
        self._declaration = declaration
        self.parameters = parameters
        self.failure_policy = failure_policy
        self.description = description

    def task_handles(self) -> tuple[TaskHandle, ...]:
        """Evaluate the declaration and return its task handles."""

        values = tuple(self._declaration())
        for value in values:
            if not isinstance(value, TaskHandle):
                raise TypeError("workflow declarations must return only TaskHandle values")
        return values

    def build(self) -> WorkflowDefinition:
        """Materialize the immutable WorkflowDefinition."""

        handles = self.task_handles()
        return WorkflowDefinition(
            workflow_id=self.workflow_id,
            version=self.version,
            tasks=tuple(handle.to_definition() for handle in handles),
            parameters=self.parameters,
            failure_policy=self.failure_policy,
            description=self.description,
        )


@overload
def task(function: Callable[P, R], /) -> TaskHandle: ...


@overload
def task(
    function: None = None,
    /,
    *,
    id: str | None = None,
    depends_on: Sequence[TaskHandle | TaskId | str] = (),
    retry_policy: RetryPolicy | None = None,
    executor_key: str = "local",
    timeout_seconds: float | None = None,
    tags: Sequence[str] = (),
    description: str | None = None,
) -> Callable[[Callable[P, R]], TaskHandle]: ...


def task(
    function: Callable[P, R] | None = None,
    /,
    *,
    id: str | None = None,
    depends_on: Sequence[TaskHandle | TaskId | str] = (),
    retry_policy: RetryPolicy | None = None,
    executor_key: str = "local",
    timeout_seconds: float | None = None,
    tags: Sequence[str] = (),
    description: str | None = None,
) -> TaskHandle | Callable[[Callable[P, R]], TaskHandle]:
    """Declare a task without executing its handler."""

    def decorate(handler: Callable[P, R]) -> TaskHandle:
        task_id = TaskId(id or handler.__name__)
        handler_ref = f"{handler.__module__}:{handler.__qualname__}"
        dependency_ids = tuple(_dependency_id(value) for value in depends_on)
        return TaskHandle(
            task_id=task_id,
            handler_ref=handler_ref,
            handler=handler,
            depends_on=dependency_ids,
            retry_policy=retry_policy or RetryPolicy(),
            executor_key=executor_key,
            timeout_seconds=timeout_seconds,
            tags=frozenset(tags),
            description=description,
        )

    if function is not None:
        return decorate(function)
    return decorate


def workflow(
    *,
    id: str,
    version: str,
    parameters: Sequence[WorkflowParameter] = (),
    failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    description: str | None = None,
) -> Callable[[WorkflowDeclaration], WorkflowBuilder]:
    """Declare a workflow lazily without executing its declaration body."""

    def decorate(declaration: WorkflowDeclaration) -> WorkflowBuilder:
        return WorkflowBuilder(
            workflow_id=WorkflowId(id),
            version=version,
            declaration=declaration,
            parameters=tuple(parameters),
            failure_policy=failure_policy,
            description=description,
        )

    return decorate


def _dependency_id(value: TaskHandle | TaskId | str) -> TaskId:
    if isinstance(value, TaskHandle):
        return value.task_id
    return TaskId(str(value))


__all__ = ["TaskHandle", "WorkflowBuilder", "task", "workflow"]
