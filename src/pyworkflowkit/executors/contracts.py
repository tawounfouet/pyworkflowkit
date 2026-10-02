"""Canonical PyWorkflowKit V2 executor contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from pyworkflowkit.authoring.workloads import Workload, WorkloadDescriptor
from pyworkflowkit.diagnostics.failure import FailureEvidence
from pyworkflowkit.diagnostics.model import Diagnostic
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId

V2_EXECUTOR_CONTRACT_VERSION = "2"
V2_EXECUTOR_PROTOCOL_METHODS: tuple[str, ...] = ("descriptor", "execute")
V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS: tuple[str, ...] = ("cancel",)


def _require_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _require_aware(value: datetime, *, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class CancellationCapability(StrEnum):
    """Executor cancellation strength."""

    UNSUPPORTED = "unsupported"
    BEST_EFFORT = "best_effort"
    CONFIRMED = "confirmed"


class CancellationStatus(StrEnum):
    """Structured cancellation command result."""

    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    UNSUPPORTED = "unsupported"
    UNCONFIRMED = "unconfirmed"
    ALREADY_TERMINAL = "already_terminal"


@dataclass(frozen=True, slots=True)
class ExecutorDescriptor:
    """Machine-readable executor identity and capability contract."""

    executor_id: str
    display_name: str
    executor_version: str
    capabilities: tuple[str, ...] = ()
    execution_modes: tuple[str, ...] = ()
    portability_constraints: tuple[str, ...] = ()
    supported_workload_kinds: tuple[str, ...] = ()
    performs_implicit_workload_retry: bool = False
    supports_execution_timeout: bool = False
    cancellation_capability: CancellationCapability = CancellationCapability.UNSUPPORTED

    def __post_init__(self) -> None:
        _require_text(self.executor_id, field_name="executor_id")
        _require_text(self.display_name, field_name="display_name")
        _require_text(self.executor_version, field_name="executor_version")
        for name in (
            "capabilities",
            "execution_modes",
            "portability_constraints",
            "supported_workload_kinds",
        ):
            values = tuple(getattr(self, name))
            for value in values:
                _require_text(value, field_name=name)
            object.__setattr__(self, name, tuple(sorted(set(values))))
        if not isinstance(self.performs_implicit_workload_retry, bool):
            raise TypeError("performs_implicit_workload_retry must be a bool")
        if not isinstance(self.supports_execution_timeout, bool):
            raise TypeError("supports_execution_timeout must be a bool")
        if not isinstance(self.cancellation_capability, CancellationCapability):
            raise TypeError("cancellation_capability must be a CancellationCapability")


@dataclass(frozen=True, slots=True)
class TaskExecutionContext:
    """Read-only context passed to trusted in-process workload callables."""

    workflow_run_id: WorkflowRunId
    task_run_id: TaskRunId
    attempt_id: TaskAttemptId
    attempt_number: int
    correlation: CorrelationContext
    dependency_outputs: Mapping[str, object] = field(default_factory=dict)
    workload_parameters: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.workflow_run_id, WorkflowRunId):
            raise TypeError("workflow_run_id must be a WorkflowRunId")
        if not isinstance(self.task_run_id, TaskRunId):
            raise TypeError("task_run_id must be a TaskRunId")
        if not isinstance(self.attempt_id, TaskAttemptId):
            raise TypeError("attempt_id must be a TaskAttemptId")
        if isinstance(self.attempt_number, bool) or not isinstance(self.attempt_number, int):
            raise TypeError("attempt_number must be an integer")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be greater than or equal to 1")
        if not isinstance(self.correlation, CorrelationContext):
            raise TypeError("correlation must be a CorrelationContext")

        outputs = dict(self.dependency_outputs)
        for key in outputs:
            _require_text(key, field_name="dependency output key")

        parameters = dict(self.workload_parameters)
        for key, value in parameters.items():
            _require_text(key, field_name="workload parameter key")
            if not isinstance(value, str):
                raise TypeError("workload parameter values must be strings")

        object.__setattr__(self, "dependency_outputs", MappingProxyType(outputs))
        object.__setattr__(self, "workload_parameters", MappingProxyType(parameters))


@dataclass(frozen=True, slots=True)
class TaskExecutionRequest:
    """One executor request for exactly one TaskAttempt."""

    task_key: str
    workload: Workload
    executor_key: str
    context: TaskExecutionContext
    deadline_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.task_key, field_name="task_key")
        _require_text(self.executor_key, field_name="executor_key")
        if not callable(self.workload) and not isinstance(self.workload, WorkloadDescriptor):
            raise TypeError("workload must be callable or implement WorkloadDescriptor")
        if not isinstance(self.context, TaskExecutionContext):
            raise TypeError("context must be a TaskExecutionContext")
        if self.deadline_at is not None:
            if not isinstance(self.deadline_at, datetime):
                raise TypeError("deadline_at must be datetime or None")
            _require_aware(self.deadline_at, field_name="deadline_at")


@dataclass(frozen=True, slots=True)
class TaskExecutionResult:
    """Normalized outcome of one executor invocation."""

    output: object = None
    failure: FailureEvidence | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if self.failure is not None and not isinstance(self.failure, FailureEvidence):
            raise TypeError("failure must be FailureEvidence or None")
        diagnostics = tuple(self.diagnostics)
        if not all(isinstance(item, Diagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain only Diagnostic values")
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def succeeded(self) -> bool:
        return self.failure is None


@dataclass(frozen=True, slots=True)
class TaskCancellationRequest:
    """Cancellation command for one concrete TaskAttempt."""

    workflow_run_id: WorkflowRunId
    task_run_id: TaskRunId
    attempt_id: TaskAttemptId
    task_key: str
    requested_at: datetime
    reason: str = "requested_by_runtime"

    def __post_init__(self) -> None:
        if not isinstance(self.workflow_run_id, WorkflowRunId):
            raise TypeError("workflow_run_id must be a WorkflowRunId")
        if not isinstance(self.task_run_id, TaskRunId):
            raise TypeError("task_run_id must be a TaskRunId")
        if not isinstance(self.attempt_id, TaskAttemptId):
            raise TypeError("attempt_id must be a TaskAttemptId")
        _require_text(self.task_key, field_name="task_key")
        if not isinstance(self.requested_at, datetime):
            raise TypeError("requested_at must be datetime")
        _require_aware(self.requested_at, field_name="requested_at")
        _require_text(self.reason, field_name="reason")


@dataclass(frozen=True, slots=True)
class TaskCancellationResult:
    """Executor-owned cancellation acknowledgement."""

    status: CancellationStatus
    attempt_id: TaskAttemptId
    reason: str
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, CancellationStatus):
            raise TypeError("status must be a CancellationStatus")
        if not isinstance(self.attempt_id, TaskAttemptId):
            raise TypeError("attempt_id must be a TaskAttemptId")
        _require_text(self.reason, field_name="reason")
        diagnostics = tuple(self.diagnostics)
        if not all(isinstance(item, Diagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain only Diagnostic values")
        object.__setattr__(self, "diagnostics", diagnostics)


@runtime_checkable
class Executor(Protocol):
    """Stable V2 execution extension boundary."""

    @property
    def descriptor(self) -> ExecutorDescriptor:
        """Return immutable executor identity and capabilities."""

    def execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        """Execute exactly one TaskAttempt."""


@runtime_checkable
class CancellableExecutor(Protocol):
    """Capability protocol for executors able to receive cancellation commands."""

    def cancel(self, request: TaskCancellationRequest) -> TaskCancellationResult:
        """Request cancellation for one concrete TaskAttempt."""


def v2_executor_contract_snapshot() -> dict[str, object]:
    return {
        "contract_version": V2_EXECUTOR_CONTRACT_VERSION,
        "protocol_members": list(V2_EXECUTOR_PROTOCOL_METHODS),
        "cancellable_protocol_members": list(V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS),
        "cancellation_statuses": [value.value for value in CancellationStatus],
        "cancellation_capabilities": [value.value for value in CancellationCapability],
    }


__all__ = [
    "CancellationCapability",
    "CancellationStatus",
    "CancellableExecutor",
    "Executor",
    "ExecutorDescriptor",
    "TaskCancellationRequest",
    "TaskCancellationResult",
    "TaskExecutionContext",
    "TaskExecutionRequest",
    "TaskExecutionResult",
    "V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS",
    "V2_EXECUTOR_CONTRACT_VERSION",
    "V2_EXECUTOR_PROTOCOL_METHODS",
    "v2_executor_contract_snapshot",
]
