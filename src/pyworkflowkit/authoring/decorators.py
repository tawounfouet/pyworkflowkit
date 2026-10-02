"""V2 decorator sugar that compiles into canonical authoring values."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import overload

from pyworkflowkit.authoring.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.authoring.io import InputDeclaration, OutputDeclaration
from pyworkflowkit.authoring.workloads import LocalCallable
from pyworkflowkit.domain.enums import FailurePolicy
from pyworkflowkit.domain.values import RetryPolicy
from pyworkflowkit.policies.timeout import TimeoutPolicy
from pyworkflowkit.policies.trigger import TriggerRule

WorkflowDeclaration = Callable[[], Sequence[TaskDefinition]]


@overload
def task(function: LocalCallable, /) -> TaskDefinition: ...


@overload
def task(
    function: None = None,
    /,
    *,
    key: str | None = None,
    depends_on: Sequence[TaskDefinition | str] = (),
    retry_policy: RetryPolicy | None = None,
    timeout_policy: TimeoutPolicy | None = None,
    trigger_rule: TriggerRule = TriggerRule.ALL_SUCCESS,
    inputs: Sequence[InputDeclaration] = (),
    outputs: Sequence[OutputDeclaration] = (),
    metadata: Mapping[str, object] | None = None,
) -> Callable[[LocalCallable], TaskDefinition]: ...


def task(
    function: LocalCallable | None = None,
    /,
    *,
    key: str | None = None,
    depends_on: Sequence[TaskDefinition | str] = (),
    retry_policy: RetryPolicy | None = None,
    timeout_policy: TimeoutPolicy | None = None,
    trigger_rule: TriggerRule = TriggerRule.ALL_SUCCESS,
    inputs: Sequence[InputDeclaration] = (),
    outputs: Sequence[OutputDeclaration] = (),
    metadata: Mapping[str, object] | None = None,
) -> TaskDefinition | Callable[[LocalCallable], TaskDefinition]:
    """Declare a canonical TaskDefinition without executing the callable."""

    def decorate(handler: LocalCallable) -> TaskDefinition:
        dependencies = tuple(
            value.key if isinstance(value, TaskDefinition) else value for value in depends_on
        )
        return TaskDefinition(
            key=key or handler.__name__,
            workload=handler,
            dependencies=dependencies,
            retry_policy=retry_policy or RetryPolicy(),
            timeout_policy=timeout_policy or TimeoutPolicy(),
            trigger_rule=trigger_rule,
            inputs=tuple(inputs),
            outputs=tuple(outputs),
            metadata=metadata or {},
        )

    if function is not None:
        return decorate(function)
    return decorate


@dataclass(frozen=True, slots=True)
class WorkflowTemplate:
    """Lazy decorator wrapper that builds one canonical WorkflowDefinition."""

    declaration: WorkflowDeclaration
    name: str
    version: str = "1"
    failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST
    metadata: Mapping[str, object] | None = None

    def build(self) -> WorkflowDefinition:
        tasks = tuple(self.declaration())
        for value in tasks:
            if not isinstance(value, TaskDefinition):
                raise TypeError("workflow declaration must return TaskDefinition values")
        return WorkflowDefinition(
            name=self.name,
            version=self.version,
            tasks=tasks,
            failure_policy=self.failure_policy,
            metadata=self.metadata or {},
        )


def workflow(
    *,
    name: str,
    version: str = "1",
    failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
    metadata: Mapping[str, object] | None = None,
) -> Callable[[WorkflowDeclaration], WorkflowTemplate]:
    """Declare a workflow lazily without executing the declaration function."""

    def decorate(declaration: WorkflowDeclaration) -> WorkflowTemplate:
        return WorkflowTemplate(
            declaration=declaration,
            name=name,
            version=version,
            failure_policy=failure_policy,
            metadata=metadata,
        )

    return decorate


__all__ = ["WorkflowTemplate", "task", "workflow"]
