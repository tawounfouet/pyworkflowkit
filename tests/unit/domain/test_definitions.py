"""Tests for static task and workflow definitions."""

from dataclasses import FrozenInstanceError

import pytest

from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import FailurePolicy
from pyworkflowkit.domain.ids import TaskId, WorkflowId
from pyworkflowkit.domain.values import RetryPolicy, WorkflowParameter
from pyworkflowkit.errors import (
    DefinitionError,
    DuplicateTaskDefinitionError,
    InvalidWorkflowDefinitionError,
)


def test_task_definition_has_safe_defaults() -> None:
    task = TaskDefinition(task_id=TaskId("fetch"))

    assert task.task_id == "fetch"
    assert task.handler_ref is None
    assert task.depends_on == ()
    assert task.retry_policy == RetryPolicy()
    assert task.executor_key == "local"
    assert task.timeout_seconds is None
    assert task.tags == frozenset()


def test_task_definition_normalizes_dependencies_and_tags() -> None:
    dependencies = [TaskId("fetch"), TaskId("validate")]
    tags = {"io", "critical"}

    task = TaskDefinition(
        task_id=TaskId("transform"),
        depends_on=dependencies,  # type: ignore[arg-type]
        tags=tags,  # type: ignore[arg-type]
    )

    dependencies.append(TaskId("other"))
    tags.add("changed")

    assert task.depends_on == (TaskId("fetch"), TaskId("validate"))
    assert task.tags == frozenset({"io", "critical"})


def test_task_definition_is_frozen() -> None:
    task = TaskDefinition(task_id=TaskId("fetch"))

    with pytest.raises(FrozenInstanceError):
        task.executor_key = "other"  # type: ignore[misc]


@pytest.mark.parametrize("task_id", ["", " ", "\t"])
def test_task_definition_rejects_blank_task_id(task_id: str) -> None:
    with pytest.raises(ValueError, match="task_id"):
        TaskDefinition(task_id=TaskId(task_id))


def test_task_definition_rejects_blank_handler_ref() -> None:
    with pytest.raises(DefinitionError, match="handler_ref"):
        TaskDefinition(
            task_id=TaskId("fetch"),
            handler_ref=" ",
        )


@pytest.mark.parametrize("executor_key", ["", " ", "\n"])
def test_task_definition_rejects_blank_executor_key(executor_key: str) -> None:
    with pytest.raises(DefinitionError, match="executor_key"):
        TaskDefinition(
            task_id=TaskId("fetch"),
            executor_key=executor_key,
        )


@pytest.mark.parametrize("timeout", [0.0, -1.0, float("inf"), float("nan")])
def test_task_definition_rejects_invalid_timeout(timeout: float) -> None:
    with pytest.raises(DefinitionError, match="timeout_seconds"):
        TaskDefinition(
            task_id=TaskId("fetch"),
            timeout_seconds=timeout,
        )


def test_task_definition_rejects_boolean_timeout() -> None:
    with pytest.raises(TypeError, match="timeout_seconds"):
        TaskDefinition(
            task_id=TaskId("fetch"),
            timeout_seconds=True,
        )


def test_task_definition_rejects_duplicate_dependencies() -> None:
    with pytest.raises(DefinitionError, match="duplicate dependencies"):
        TaskDefinition(
            task_id=TaskId("publish"),
            depends_on=(TaskId("transform"), TaskId("transform")),
        )


def test_task_definition_rejects_self_dependency() -> None:
    with pytest.raises(DefinitionError, match="cannot depend on itself"):
        TaskDefinition(
            task_id=TaskId("fetch"),
            depends_on=(TaskId("fetch"),),
        )


def test_task_definition_rejects_blank_dependency_id() -> None:
    with pytest.raises(ValueError, match="dependency_id"):
        TaskDefinition(
            task_id=TaskId("publish"),
            depends_on=(TaskId(" "),),
        )


def test_task_definition_rejects_blank_tag() -> None:
    with pytest.raises(DefinitionError, match="tag"):
        TaskDefinition(
            task_id=TaskId("fetch"),
            tags=frozenset({"io", " "}),
        )


def test_task_definition_rejects_invalid_retry_policy_type() -> None:
    with pytest.raises(TypeError, match="retry_policy"):
        TaskDefinition(
            task_id=TaskId("fetch"),
            retry_policy="invalid",  # type: ignore[arg-type]
        )


def test_workflow_definition_preserves_static_semantics() -> None:
    fetch = TaskDefinition(task_id=TaskId("fetch"))
    transform = TaskDefinition(
        task_id=TaskId("transform"),
        depends_on=(TaskId("fetch"),),
        retry_policy=RetryPolicy(max_attempts=3),
        executor_key="local",
        timeout_seconds=30.0,
        tags=frozenset({"transform"}),
    )
    parameter = WorkflowParameter(name="source_uri")

    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("example"),
        version="1",
        tasks=(fetch, transform),
        parameters=(parameter,),
        failure_policy=FailurePolicy.FAIL_FAST,
    )

    assert workflow.workflow_id == "example"
    assert workflow.version == "1"
    assert workflow.tasks == (fetch, transform)
    assert workflow.parameters == (parameter,)
    assert workflow.failure_policy is FailurePolicy.FAIL_FAST


def test_workflow_definition_normalizes_collections() -> None:
    tasks = [TaskDefinition(task_id=TaskId("fetch"))]
    parameters = [WorkflowParameter(name="source")]

    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("example"),
        version="1",
        tasks=tasks,  # type: ignore[arg-type]
        parameters=parameters,  # type: ignore[arg-type]
    )

    tasks.append(TaskDefinition(task_id=TaskId("publish")))
    parameters.append(WorkflowParameter(name="other"))

    assert tuple(task.task_id for task in workflow.tasks) == (TaskId("fetch"),)
    assert tuple(parameter.name for parameter in workflow.parameters) == ("source",)


@pytest.mark.parametrize("workflow_id", ["", " ", "\n"])
def test_workflow_definition_rejects_blank_workflow_id(workflow_id: str) -> None:
    with pytest.raises(ValueError, match="workflow_id"):
        WorkflowDefinition(
            workflow_id=WorkflowId(workflow_id),
            version="1",
            tasks=(TaskDefinition(task_id=TaskId("fetch")),),
        )


@pytest.mark.parametrize("version", ["", " ", "\t"])
def test_workflow_definition_rejects_blank_version(version: str) -> None:
    with pytest.raises(DefinitionError, match="version"):
        WorkflowDefinition(
            workflow_id=WorkflowId("example"),
            version=version,
            tasks=(TaskDefinition(task_id=TaskId("fetch")),),
        )


def test_workflow_definition_rejects_empty_task_set() -> None:
    with pytest.raises(
        InvalidWorkflowDefinitionError,
        match="at least one task",
    ) as exc_info:
        WorkflowDefinition(
            workflow_id=WorkflowId("empty"),
            version="1",
            tasks=(),
        )

    assert exc_info.value.workflow_id == WorkflowId("empty")


def test_workflow_definition_rejects_duplicate_task_ids() -> None:
    first = TaskDefinition(task_id=TaskId("fetch"))
    second = TaskDefinition(task_id=TaskId("fetch"))

    with pytest.raises(DuplicateTaskDefinitionError) as exc_info:
        WorkflowDefinition(
            workflow_id=WorkflowId("duplicate"),
            version="1",
            tasks=(first, second),
        )

    assert exc_info.value.workflow_id == WorkflowId("duplicate")
    assert exc_info.value.task_id == TaskId("fetch")


def test_workflow_definition_rejects_duplicate_parameter_names() -> None:
    with pytest.raises(
        InvalidWorkflowDefinitionError,
        match="duplicate parameter",
    ):
        WorkflowDefinition(
            workflow_id=WorkflowId("parameters"),
            version="1",
            tasks=(TaskDefinition(task_id=TaskId("fetch")),),
            parameters=(
                WorkflowParameter(name="source"),
                WorkflowParameter(name="source"),
            ),
        )


def test_workflow_definition_rejects_invalid_task_member() -> None:
    with pytest.raises(TypeError, match="TaskDefinition"):
        WorkflowDefinition(
            workflow_id=WorkflowId("invalid"),
            version="1",
            tasks=("not-a-task",),  # type: ignore[arg-type]
        )


def test_workflow_definition_rejects_invalid_parameter_member() -> None:
    with pytest.raises(TypeError, match="WorkflowParameter"):
        WorkflowDefinition(
            workflow_id=WorkflowId("invalid"),
            version="1",
            tasks=(TaskDefinition(task_id=TaskId("fetch")),),
            parameters=("not-a-parameter",),  # type: ignore[arg-type]
        )


def test_workflow_definition_rejects_invalid_failure_policy_type() -> None:
    with pytest.raises(TypeError, match="failure_policy"):
        WorkflowDefinition(
            workflow_id=WorkflowId("invalid"),
            version="1",
            tasks=(TaskDefinition(task_id=TaskId("fetch")),),
            failure_policy="FAIL_FAST",  # type: ignore[arg-type]
        )


def test_workflow_definition_does_not_validate_unknown_dependency_yet() -> None:
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("graph-validation-is-separate"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("transform"),
                depends_on=(TaskId("missing-fetch"),),
            ),
        ),
    )

    assert workflow.tasks[0].depends_on == (TaskId("missing-fetch"),)
