"""Canonical task and handler example using the package-root API."""

from __future__ import annotations

import json

from pyworkflowkit._compat.v1_root import TaskHandle, WorkflowRuntime, task, workflow


@task(description="Fetch a deterministic row count.")
def fetch() -> dict[str, int]:
    return {"rows": 3}


@workflow(id="examples.tasks-and-handlers", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (fetch,)


runtime = WorkflowRuntime()
runtime.register(fetch.handler_ref, fetch.handler)

definition = demo.build()
run = runtime.run(definition)

print(
    json.dumps(
        {
            "handler_ref": fetch.handler_ref,
            "status": run.status.value,
            "task_id": str(fetch.task_id),
        },
        sort_keys=True,
    )
)
