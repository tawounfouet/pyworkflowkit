"""Executor port and execution contracts."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
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


class TimeoutCapability(StrEnum):
    """Timeout strength explicitly supported by an Executor."""

    NONE = "none"
    SOFT = "soft"
    HARD = "hard"


class CancellationCapability(StrEnum):
    """Cancellation strength explicitly supported by an Executor."""

    NONE = "none"
    COOPERATIVE = "cooperative"
    HARD = "hard"


@dataclass(frozen=True, slots=True)
class ExecutorCapabilities:
    """Small immutable contract describing Executor runtime capabilities."""

    supports_parallelism: bool = False
    timeout: TimeoutCapability = TimeoutCapability.NONE
    cancellation: CancellationCapability = CancellationCapability.NONE
    max_concurrency: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.timeout, TimeoutCapability):
            raise TypeError("timeout must be a TimeoutCapability")
        if not isinstance(self.cancellation, CancellationCapability):
            raise TypeError("cancellation must be a CancellationCapability")
        if isinstance(self.max_concurrency, bool) or not isinstance(self.max_concurrency, int):
            raise TypeError("max_concurrency must be an integer")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be greater than or equal to 1")
        if not self.supports_parallelism and self.max_concurrency != 1:
            raise ValueError("non-parallel executors must declare max_concurrency=1")

    @property
    def supports_timeout(self) -> bool:
        return self.timeout is not TimeoutCapability.NONE

    @property
    def supports_cancellation(self) -> bool:
        return self.cancellation is not CancellationCapability.NONE

    @property
    def supports_hard_timeout(self) -> bool:
        """Compatibility view for the pre-M25 capability contract."""

        return self.timeout is TimeoutCapability.HARD

    @property
    def supports_hard_cancellation(self) -> bool:
        """Compatibility view for the pre-M25 capability contract."""

        return self.cancellation is CancellationCapability.HARD


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
    "CancellationCapability",
    "ContextHandler",
    "Executor",
    "ExecutorCapabilities",
    "RunContext",
    "TaskHandler",
    "TimeoutCapability",
    "ZeroArgumentHandler",
]
