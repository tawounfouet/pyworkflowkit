"""Canonical RuntimeEvent inspection example."""

from __future__ import annotations

import json

from pyworkflowkit._compat.v1_root import TaskHandle, WorkflowRuntime, task, workflow


@task
def prepare() -> str:
    return "ready"


@task(depends_on=(prepare,))
def publish() -> str:
    return "published"


@workflow(id="examples.events", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (prepare, publish)


runtime = WorkflowRuntime()
for handle in demo.task_handles():
    runtime.register(handle.handler_ref, handle.handler)

definition = demo.build()
run = runtime.run(definition)
events = runtime.events(run.run_id)

print(
    json.dumps(
        {
            "event_types": [event.event_type.value for event in events],
            "sequences": [event.event_sequence for event in events],
        },
        sort_keys=True,
    )
)
