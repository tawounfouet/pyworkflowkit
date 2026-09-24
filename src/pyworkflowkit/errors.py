"""Public exception hierarchy for PyWorkflowKit."""

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
    "DefinitionError",
    "DomainError",
    "DuplicateTaskDefinitionError",
    "InvalidStateTransitionError",
    "InvalidWorkflowDefinitionError",
    "PyWorkflowKitError",
    "TerminalStateError",
]
