"""Immutable workflow and task definitions."""

from dataclasses import dataclass, field
from math import isfinite

from pyworkflowkit.domain.enums import FailurePolicy
from pyworkflowkit.domain.ids import TaskId, WorkflowId, validate_non_empty_identifier
from pyworkflowkit.domain.values import RetryPolicy, WorkflowParameter
from pyworkflowkit.errors import (
    DefinitionError,
    DuplicateTaskDefinitionError,
    InvalidWorkflowDefinitionError,
)


def _require_non_empty_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise DefinitionError(f"{field_name} must not be empty.")
    return value


def _validate_timeout(value: float | None) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("timeout_seconds must be a finite number.")
    if not isfinite(value):
        raise DefinitionError("timeout_seconds must be finite.")
    if value <= 0:
        raise DefinitionError("timeout_seconds must be greater than 0.")


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    """Static definition of one workflow task."""

    task_id: TaskId
    handler_ref: str | None = None
    depends_on: tuple[TaskId, ...] = ()
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    executor_key: str = "local"
    timeout_seconds: float | None = None
    tags: frozenset[str] = field(default_factory=frozenset)
    description: str | None = None

    def __post_init__(self) -> None:
        validate_non_empty_identifier(str(self.task_id), field_name="task_id")

        if self.handler_ref is not None:
            _require_non_empty_text(self.handler_ref, field_name="handler_ref")
        _require_non_empty_text(self.executor_key, field_name="executor_key")
        _validate_timeout(self.timeout_seconds)

        dependencies = tuple(self.depends_on)
        if len(dependencies) != len(set(dependencies)):
            raise DefinitionError(
                f"Task '{self.task_id}' declares duplicate dependencies."
            )
        if self.task_id in dependencies:
            raise DefinitionError(
                f"Task '{self.task_id}' cannot depend on itself."
            )

        for dependency_id in dependencies:
            validate_non_empty_identifier(
                str(dependency_id),
                field_name="dependency_id",
            )

        tags = frozenset(self.tags)
        for tag in tags:
            _require_non_empty_text(tag, field_name="tag")

        if not isinstance(self.retry_policy, RetryPolicy):
            raise TypeError("retry_policy must be a RetryPolicy.")

        object.__setattr__(self, "depends_on", dependencies)
        object.__setattr__(self, "tags", tags)


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """Immutable static definition of a workflow DAG."""

    workflow_id: WorkflowId
    version: str
    tasks: tuple[TaskDefinition, ...]
    parameters: tuple[WorkflowParameter, ...] = ()
    failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST
    description: str | None = None

    def __post_init__(self) -> None:
        validate_non_empty_identifier(
            str(self.workflow_id),
            field_name="workflow_id",
        )
        _require_non_empty_text(self.version, field_name="version")

        tasks = tuple(self.tasks)
        if not tasks:
            raise InvalidWorkflowDefinitionError(
                workflow_id=self.workflow_id,
                reason="workflow must contain at least one task",
            )

        seen_task_ids: set[TaskId] = set()
        for task in tasks:
            if not isinstance(task, TaskDefinition):
                raise TypeError("tasks must contain only TaskDefinition values.")
            if task.task_id in seen_task_ids:
                raise DuplicateTaskDefinitionError(
                    workflow_id=self.workflow_id,
                    task_id=task.task_id,
                )
            seen_task_ids.add(task.task_id)

        parameters = tuple(self.parameters)
        seen_parameter_names: set[str] = set()
        for parameter in parameters:
            if not isinstance(parameter, WorkflowParameter):
                raise TypeError(
                    "parameters must contain only WorkflowParameter values."
                )
            if parameter.name in seen_parameter_names:
                raise InvalidWorkflowDefinitionError(
                    workflow_id=self.workflow_id,
                    reason=(
                        f"workflow declares duplicate parameter "
                        f"'{parameter.name}'"
                    ),
                )
            seen_parameter_names.add(parameter.name)

        if not isinstance(self.failure_policy, FailurePolicy):
            raise TypeError("failure_policy must be a FailurePolicy.")

        object.__setattr__(self, "tasks", tasks)
        object.__setattr__(self, "parameters", parameters)


__all__ = ["TaskDefinition", "WorkflowDefinition"]
