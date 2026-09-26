"""Tests for the lazy declarative API."""

from pyworkflowkit import RetryPolicy, TaskId
from pyworkflowkit.declarative import TaskHandle, WorkflowBuilder, task, workflow


def test_task_decoration_does_not_execute_handler() -> None:
    calls = 0

    @task
    def fetch() -> str:
        nonlocal calls
        calls += 1
        return "data"

    assert isinstance(fetch, TaskHandle)
    assert fetch.task_id == TaskId("fetch")
    assert calls == 0


def test_task_decorator_builds_explicit_dependency_metadata() -> None:
    @task
    def fetch() -> str:
        return "data"

    @task(depends_on=(fetch,), retry_policy=RetryPolicy(max_attempts=2))
    def transform() -> str:
        return "transformed"

    definition = transform.to_definition()

    assert definition.depends_on == (TaskId("fetch"),)
    assert definition.retry_policy.max_attempts == 2
    assert definition.handler_ref.endswith(".transform")


def test_workflow_decoration_is_lazy_until_build() -> None:
    declaration_calls = 0

    @task
    def fetch() -> str:
        return "data"

    @workflow(id="demo.lazy", version="1")
    def demo() -> tuple[TaskHandle, ...]:
        nonlocal declaration_calls
        declaration_calls += 1
        return (fetch,)

    assert isinstance(demo, WorkflowBuilder)
    assert declaration_calls == 0

    definition = demo.build()

    assert declaration_calls == 1
    assert definition.workflow_id == "demo.lazy"
    assert definition.tasks[0].task_id == TaskId("fetch")


def test_workflow_build_rejects_non_task_handles() -> None:
    @workflow(id="bad", version="1")
    def bad():  # type: ignore[no-untyped-def]
        return ("not-a-task",)

    try:
        bad.build()
    except TypeError as exc:
        assert "TaskHandle" in str(exc)
    else:
        raise AssertionError("expected TypeError")
