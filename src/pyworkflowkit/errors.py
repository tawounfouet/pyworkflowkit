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
    "DuplicateTaskDefinitionError",
    "GraphError",
    "InvalidExecutionPlanError",
    "InvalidStateTransitionError",
    "InvalidWorkflowDefinitionError",
    "PlanningError",
    "PlanningInvariantError",
    "PyWorkflowKitError",
    "SelfDependencyError",
    "TerminalStateError",
    "UnknownDependencyError",
]
