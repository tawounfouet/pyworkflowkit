"""Executor port and execution contracts."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol, TypeAlias, runtime_checkable

from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.ids import (
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowRunId,
    validate_non_empty_identifier,
)
from pyworkflowkit.domain.values import TaskResult


def _freeze_mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class ExecutorCapabilities:
    """Capabilities declared by an Executor implementation."""

    supports_parallelism: bool = False
    supports_hard_timeout: bool = False
    supports_hard_cancellation: bool = False


@dataclass(frozen=True, slots=True)
class RunContext:
    """Read-only execution context passed to a task handler."""

    workflow_run_id: WorkflowRunId
    task_run_id: TaskRunId
    attempt_id: TaskAttemptId
    task_id: TaskId
    attempt_number: int
    workflow_parameters: Mapping[str, object] = field(default_factory=dict)
    dependency_outputs: Mapping[TaskId, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_identifier(
            str(self.workflow_run_id),
            field_name="workflow_run_id",
        )
        validate_non_empty_identifier(str(self.task_run_id), field_name="task_run_id")
        validate_non_empty_identifier(str(self.attempt_id), field_name="attempt_id")
        validate_non_empty_identifier(str(self.task_id), field_name="task_id")

        if isinstance(self.attempt_number, bool) or not isinstance(self.attempt_number, int):
            raise TypeError("attempt_number must be an integer.")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be greater than or equal to 1.")

        object.__setattr__(
            self,
            "workflow_parameters",
            _freeze_mapping(self.workflow_parameters),
        )
        object.__setattr__(
            self,
            "dependency_outputs",
            MappingProxyType(dict(self.dependency_outputs)),
        )


ZeroArgumentHandler: TypeAlias = Callable[[], object]
ContextHandler: TypeAlias = Callable[[RunContext], object]
TaskHandler: TypeAlias = ZeroArgumentHandler | ContextHandler


@runtime_checkable
class Executor(Protocol):
    """Port implemented by concrete workload executors."""

    @property
    def key(self) -> str:
        """Stable registry key for this executor."""

    @property
    def capabilities(self) -> ExecutorCapabilities:
        """Capabilities supported by this executor."""

    def execute(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> TaskResult:
        """Execute one task handler and normalize its result."""


__all__ = [
    "ContextHandler",
    "Executor",
    "ExecutorCapabilities",
    "RunContext",
    "TaskHandler",
    "ZeroArgumentHandler",
]
