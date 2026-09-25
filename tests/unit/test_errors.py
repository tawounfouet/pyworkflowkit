"""Tests for the public exception hierarchy."""

from pyworkflowkit.domain.ids import TaskId, WorkflowId
from pyworkflowkit.errors import (
    CycleDetectedError,
    DefinitionError,
    DomainError,
    DuplicateDependencyError,
    DuplicateHandlerRegistrationError,
    DuplicateTaskDefinitionError,
    ExecutorError,
    GraphError,
    HandlerNotFoundError,
    InvalidExecutionPlanError,
    InvalidHandlerError,
    InvalidStateTransitionError,
    InvalidWorkflowDefinitionError,
    PlanningError,
    PlanningInvariantError,
    PyWorkflowKitError,
    SelfDependencyError,
    TaskExecutionError,
    TerminalStateError,
    UnknownDependencyError,
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


def test_unknown_dependency_error_exposes_graph_context() -> None:
    error = UnknownDependencyError(
        task_id=TaskId("transform"),
        dependency_id=TaskId("fetch"),
    )

    assert isinstance(error, GraphError)
    assert error.task_id == TaskId("transform")
    assert error.dependency_id == TaskId("fetch")
    assert "unknown task 'fetch'" in str(error)


def test_self_dependency_error_exposes_task() -> None:
    error = SelfDependencyError(task_id=TaskId("A"))

    assert isinstance(error, GraphError)
    assert error.task_id == TaskId("A")


def test_duplicate_dependency_error_exposes_edge_context() -> None:
    error = DuplicateDependencyError(
        task_id=TaskId("B"),
        dependency_id=TaskId("A"),
    )

    assert isinstance(error, GraphError)
    assert error.task_id == TaskId("B")
    assert error.dependency_id == TaskId("A")


def test_cycle_error_normalizes_task_order() -> None:
    error = CycleDetectedError(
        task_ids=(TaskId("C"), TaskId("A"), TaskId("B")),
    )

    assert isinstance(error, GraphError)
    assert error.task_ids == (TaskId("A"), TaskId("B"), TaskId("C"))
    assert "A, B, C" in str(error)


def test_invalid_execution_plan_error_exposes_reason() -> None:
    error = InvalidExecutionPlanError(reason="duplicate task")

    assert isinstance(error, PlanningError)
    assert error.reason == "duplicate task"
    assert "duplicate task" in str(error)


def test_planning_invariant_error_exposes_reason() -> None:
    error = PlanningInvariantError(reason="graph mismatch")

    assert isinstance(error, PlanningError)
    assert error.reason == "graph mismatch"
    assert "graph mismatch" in str(error)


def test_executor_error_hierarchy_and_context() -> None:
    duplicate = DuplicateHandlerRegistrationError(handler_ref="module:handler")
    missing = HandlerNotFoundError(handler_ref="missing:handler")
    invalid = InvalidHandlerError(task_id=TaskId("task"), reason="bad signature")
    execution = TaskExecutionError(
        task_id=TaskId("task"),
        handler_ref="module:handler",
        error_type="ValueError",
        error_message="boom",
    )

    assert isinstance(duplicate, ExecutorError)
    assert duplicate.handler_ref == "module:handler"
    assert isinstance(missing, ExecutorError)
    assert missing.handler_ref == "missing:handler"
    assert invalid.task_id == TaskId("task")
    assert invalid.reason == "bad signature"
    assert execution.error_type == "ValueError"
    assert execution.error_message == "boom"


def test_invalid_state_transition_exposes_structured_context() -> None:
    error = InvalidStateTransitionError(
        entity_type="TaskRun",
        entity_id="task-run-1",
        current_status="PENDING",
        target_status="SUCCEEDED",
    )

    assert isinstance(error, DomainError)
    assert error.entity_type == "TaskRun"
    assert error.entity_id == "task-run-1"
    assert error.current_status == "PENDING"
    assert error.target_status == "SUCCEEDED"
    assert "PENDING" in str(error)
    assert "SUCCEEDED" in str(error)


def test_terminal_state_error_is_specialized_transition_error() -> None:
    error = TerminalStateError(
        entity_type="WorkflowRun",
        entity_id="run-1",
        current_status="SUCCEEDED",
        target_status="FAILED",
    )

    assert isinstance(error, InvalidStateTransitionError)
    assert isinstance(error, DomainError)
    assert "terminal" in str(error)
