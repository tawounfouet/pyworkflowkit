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


__all__ = [
    "DefinitionError",
    "DuplicateTaskDefinitionError",
    "InvalidWorkflowDefinitionError",
    "PyWorkflowKitError",
]
