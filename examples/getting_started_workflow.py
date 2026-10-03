"""Import-safe decorated workflow used by the RQ-04 CLI journey."""

from pyworkflowkit._compat.v1_root import RunContext, TaskHandle, TaskId, task, workflow


@task
def fetch() -> int:
    return 10


@task(depends_on=(fetch,))
def publish(context: RunContext) -> int:
    return int(context.dependency_outputs[TaskId("fetch")])


@workflow(id="docs.cli", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (fetch, publish)


__all__ = ["demo"]
