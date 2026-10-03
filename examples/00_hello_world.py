"""Minimal public-API PyWorkflowKit quickstart."""

from __future__ import annotations

import json

from pyworkflowkit._compat.v1_root import RunContext, TaskHandle, TaskId, WorkflowRuntime, task, workflow


@task
def fetch() -> int:
    return 21


@task(depends_on=(fetch,))
def transform(context: RunContext) -> int:
    return int(context.dependency_outputs[TaskId("fetch")]) * 2


@workflow(id="hello-world", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (fetch, transform)


runtime = WorkflowRuntime()
for handle in demo.task_handles():
    runtime.register(handle.handler_ref, handle.handler)

definition = demo.build()
run = runtime.run(definition)
manifest = runtime.manifest(definition, run.run_id)

print(
    json.dumps(
        {
            "workflow_id": str(run.workflow_id),
            "run_id": str(run.run_id),
            "status": run.status.value,
            "event_count": len(runtime.events(run.run_id)),
            "manifest_status": manifest.status,
        },
        sort_keys=True,
    )
)
