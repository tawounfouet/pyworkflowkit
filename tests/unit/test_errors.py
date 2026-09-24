"""Tests for the public exception hierarchy."""

from pyworkflowkit.domain.ids import TaskId, WorkflowId
from pyworkflowkit.errors import (
    DefinitionError,
    DuplicateTaskDefinitionError,
    InvalidWorkflowDefinitionError,
    PyWorkflowKitError,
)


def test_public_error_root_is_catchable_as_exception() -> None:
    error = PyWorkflowKitError("boom")

    assert isinstance(error, Exception)
    assert str(error) == "boom"


def test_definition_errors_are_catchable_from_public_root() -> None:
    error = DefinitionError("invalid definition")

    assert isinstance(error, PyWorkflowKitError)


def test_invalid_workflow_definition_exposes_structured_context() -> None:
    error = InvalidWorkflowDefinitionError(
        workflow_id=WorkflowId("workflow"),
        reason="empty task set",
    )

    assert error.workflow_id == WorkflowId("workflow")
    assert error.reason == "empty task set"
    assert "empty task set" in str(error)


def test_duplicate_task_definition_exposes_structured_context() -> None:
    error = DuplicateTaskDefinitionError(
        workflow_id=WorkflowId("workflow"),
        task_id=TaskId("fetch"),
    )

    assert error.workflow_id == WorkflowId("workflow")
    assert error.task_id == TaskId("fetch")
    assert "fetch" in str(error)
