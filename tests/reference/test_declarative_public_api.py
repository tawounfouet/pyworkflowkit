"""M19 declarative API acceptance coverage."""

from pyworkflowkit import TaskHandle, WorkflowRuntime, task, workflow


def test_decorated_workflow_executes_through_public_runtime() -> None:
    executed: list[str] = []

    @task
    def fetch() -> str:
        executed.append("fetch")
        return "raw"

    @task(depends_on=(fetch,))
    def publish() -> str:
        executed.append("publish")
        return "done"

    @workflow(id="demo.decorated", version="1")
    def demo() -> tuple[TaskHandle, ...]:
        return (fetch, publish)

    assert executed == []

    definition = demo.build()
    assert executed == []

    runtime = WorkflowRuntime()
    for handle in demo.task_handles():
        runtime.register(handle.handler_ref, handle.handler)

    run = runtime.run(definition)

    assert run.status.value == "SUCCEEDED"
    assert executed == ["fetch", "publish"]
