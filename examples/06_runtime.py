"""Canonical WorkflowRuntime execution example."""

from __future__ import annotations

import json

from pyworkflowkit._compat.v1_root import TaskHandle, WorkflowRuntime, task, workflow


@task
def hello() -> str:
    return "hello"


@workflow(id="examples.runtime", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (hello,)


runtime = WorkflowRuntime()
for handle in demo.task_handles():
    runtime.register(handle.handler_ref, handle.handler)

definition = demo.build()
run = runtime.run(definition)

print(
    json.dumps(
        {
            "event_count": len(runtime.events(run.run_id)),
            "run_id": str(run.run_id),
            "status": run.status.value,
        },
        sort_keys=True,
    )
)
