"""Public exception hierarchy for PyWorkflowKit."""

from collections.abc import Iterable

from pyworkflowkit.domain.ids import TaskId, WorkflowId


class PyWorkflowKitError(Exception):
    """Base class for public PyWorkflowKit exceptions."""


class DefinitionError(PyWorkflowKitError):
    """Base class for static workflow-definition errors."""


class InvalidWorkflowDefinitionError(DefinitionError):
    """Raised when a workflow definition violates a workflow-level invariant."""

    def __init__(self, *, workflow_id: WorkflowId, reason: str) -> None:
        self.workflow_id = workflow_id
        self.reason = reason
        super().__init__(f"Workflow '{workflow_id}' is invalid: {reason}.")


class DuplicateTaskDefinitionError(DefinitionError):
    """Raised when a workflow declares the same task identifier twice."""

    def __init__(
        self,
        *,
        workflow_id: WorkflowId,
        task_id: TaskId,
    ) -> None:
        self.workflow_id = workflow_id
        self.task_id = task_id
        super().__init__(f"Workflow '{workflow_id}' declares duplicate task '{task_id}'.")


class GraphError(PyWorkflowKitError):
    """Base class for dependency-graph errors."""


class UnknownDependencyError(GraphError):
    """Raised when a graph edge references a task absent from the workflow."""

    def __init__(
        self,
        *,
        task_id: TaskId,
        dependency_id: TaskId,
    ) -> None:
        self.task_id = task_id
        self.dependency_id = dependency_id
        super().__init__(f"Task '{task_id}' depends on unknown task '{dependency_id}'.")


class SelfDependencyError(GraphError):
    """Raised when a task depends directly on itself."""

    def __init__(self, *, task_id: TaskId) -> None:
        self.task_id = task_id
        super().__init__(f"Task '{task_id}' cannot depend on itself.")


class DuplicateDependencyError(GraphError):
    """Raised when the same directed dependency edge is declared more than once."""

    def __init__(
        self,
        *,
        task_id: TaskId,
        dependency_id: TaskId,
    ) -> None:
        self.task_id = task_id
        self.dependency_id = dependency_id
        super().__init__(f"Task '{task_id}' declares duplicate dependency '{dependency_id}'.")


class CycleDetectedError(GraphError):
    """Raised when a dependency graph contains at least one directed cycle."""

    def __init__(self, *, task_ids: Iterable[TaskId]) -> None:
        self.task_ids = tuple(sorted(task_ids, key=str))
        rendered = ", ".join(str(task_id) for task_id in self.task_ids)
        super().__init__(f"Workflow dependency graph contains a cycle involving tasks: {rendered}.")


class PlanningError(PyWorkflowKitError):
    """Base class for static planning and runtime-readiness errors."""


class InvalidExecutionPlanError(PlanningError):
    """Raised when an ExecutionPlan value violates its own invariants."""

    def __init__(self, *, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Execution plan is invalid: {reason}.")


class PlanningInvariantError(PlanningError):
    """Raised when planning inputs violate a required precondition."""

    def __init__(self, *, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Planning invariant violated: {reason}.")


class ExecutorError(PyWorkflowKitError):
    """Base class for workload-execution errors."""


class ExecutorNotFoundError(ExecutorError):
    """Raised when the Runner has no executor for a requested executor key."""

    def __init__(self, *, executor_key: str) -> None:
        self.executor_key = executor_key
        super().__init__(f"Executor '{executor_key}' is not available.")


class DuplicateHandlerRegistrationError(ExecutorError):
    """Raised when a handler reference is registered more than once."""

    def __init__(self, *, handler_ref: str) -> None:
        self.handler_ref = handler_ref
        super().__init__(f"Handler reference '{handler_ref}' is already registered.")


class HandlerNotFoundError(ExecutorError):
    """Raised when an explicit handler reference cannot be resolved."""

    def __init__(self, *, handler_ref: str) -> None:
        self.handler_ref = handler_ref
        super().__init__(f"Handler reference '{handler_ref}' is not registered.")


class InvalidHandlerError(ExecutorError):
    """Raised when a handler cannot satisfy the executor contract."""

    def __init__(self, *, task_id: TaskId, reason: str) -> None:
        self.task_id = task_id
        self.reason = reason
        super().__init__(f"Handler for task '{task_id}' is invalid: {reason}.")


class TaskExecutionError(ExecutorError):
    """Raised when a task handler raises an ordinary Python exception."""

    def __init__(
        self,
        *,
        task_id: TaskId,
        handler_ref: str | None,
        error_type: str,
        error_message: str,
        error_category: str | None = None,
    ) -> None:
        self.task_id = task_id
        self.handler_ref = handler_ref
        self.error_type = error_type
        self.error_message = error_message
        self.error_category = error_category or error_type
        rendered_ref = handler_ref or "<direct-handler>"
        super().__init__(
            f"Task '{task_id}' handler '{rendered_ref}' failed with {error_type}: {error_message}"
        )


class RuntimeErrorBase(PyWorkflowKitError):
    """Base class for workflow runtime orchestration errors."""


class InvalidWorkflowParametersError(RuntimeErrorBase):
    """Raised when supplied workflow parameters do not match the definition."""

    def __init__(self, *, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Workflow parameters are invalid: {reason}.")


class RuntimeInvariantError(RuntimeErrorBase):
    """Raised when Runner state violates an internal runtime invariant."""

    def __init__(self, *, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Runtime invariant violated: {reason}.")


class ManifestError(PyWorkflowKitError):
    """Base class for execution-manifest errors."""


class ManifestNotReadyError(ManifestError):
    """Raised when final evidence is requested for a non-terminal run."""

    def __init__(self, *, run_id: str, status: str) -> None:
        self.run_id = run_id
        self.status = status
        super().__init__(
            f"Run '{run_id}' cannot produce a final manifest while status is {status}."
        )


class ManifestInvariantError(ManifestError):
    """Raised when persisted runtime evidence is internally inconsistent."""

    def __init__(self, *, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Manifest invariant violated: {reason}.")


class ManifestSerializationError(ManifestError):
    """Raised when runtime evidence cannot be represented as portable JSON."""

    def __init__(self, *, path: str, value_type: str) -> None:
        self.path = path
        self.value_type = value_type
        super().__init__(f"Manifest value at '{path}' is not JSON-portable: {value_type}.")


class SerializationError(PyWorkflowKitError):
    """Raised when a boundary value cannot be serialized portably."""

    def __init__(
        self,
        *,
        path: str,
        value_type: str,
        reason: str,
    ) -> None:
        self.path = path
        self.value_type = value_type
        self.reason = reason
        super().__init__(f"Serialization failed at '{path}' for {value_type}: {reason}.")


class MetadataStoreError(PyWorkflowKitError):
    """Base class for runtime metadata persistence errors."""


class MetadataNotFoundError(MetadataStoreError):
    """Raised when required runtime metadata does not exist."""

    def __init__(self, *, entity_type: str, entity_id: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} '{entity_id}' was not found.")


class DuplicateMetadataError(MetadataStoreError):
    """Raised when a persistence identity or uniqueness invariant is duplicated."""

    def __init__(self, *, entity_type: str, entity_id: str) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} '{entity_id}' already exists.")


class UnitOfWorkStateError(MetadataStoreError):
    """Raised when a UnitOfWork lifecycle operation is invalid."""

    def __init__(self, *, reason: str) -> None:
        self.reason = reason
        super().__init__(f"UnitOfWork state is invalid: {reason}.")


class DomainError(PyWorkflowKitError):
    """Base class for runtime domain-invariant violations."""


class InvalidStateTransitionError(DomainError):
    """Raised when a non-terminal runtime entity cannot make a requested transition."""

    def __init__(
        self,
        *,
        entity_type: str,
        entity_id: str,
        current_status: str,
        target_status: str,
    ) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"{entity_type} '{entity_id}' cannot transition "
            f"from {current_status} to {target_status}."
        )


class TerminalStateError(InvalidStateTransitionError):
    """Raised when a transition is requested from an absorbing terminal state."""

    def __init__(
        self,
        *,
        entity_type: str,
        entity_id: str,
        current_status: str,
        target_status: str,
    ) -> None:
        super().__init__(
            entity_type=entity_type,
            entity_id=entity_id,
            current_status=current_status,
            target_status=target_status,
        )
        self.args = (
            f"{entity_type} '{entity_id}' is terminal in {current_status} "
            f"and cannot transition to {target_status}.",
        )


__all__ = [
    "CycleDetectedError",
    "DefinitionError",
    "DomainError",
    "DuplicateDependencyError",
    "DuplicateHandlerRegistrationError",
    "DuplicateTaskDefinitionError",
    "ExecutorError",
    "ExecutorNotFoundError",
    "GraphError",
    "HandlerNotFoundError",
    "InvalidExecutionPlanError",
    "InvalidHandlerError",
    "InvalidStateTransitionError",
    "InvalidWorkflowDefinitionError",
    "InvalidWorkflowParametersError",
    "ManifestError",
    "ManifestInvariantError",
    "ManifestNotReadyError",
    "ManifestSerializationError",
    "MetadataNotFoundError",
    "MetadataStoreError",
    "DuplicateMetadataError",
    "PlanningError",
    "PlanningInvariantError",
    "PyWorkflowKitError",
    "RuntimeErrorBase",
    "RuntimeInvariantError",
    "SerializationError",
    "SelfDependencyError",
    "TaskExecutionError",
    "TerminalStateError",
    "UnitOfWorkStateError",
    "UnknownDependencyError",
]
