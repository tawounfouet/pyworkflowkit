"""Canonical RunContext dependency-output and parameter example."""

from __future__ import annotations

import json

from pyworkflowkit._compat.v1_root import (
    RunContext,
    TaskHandle,
    TaskId,
    WorkflowParameter,
    WorkflowRuntime,
    task,
    workflow,
)


@task
def fetch() -> int:
    return 7


@task(depends_on=(fetch,))
def transform(context: RunContext) -> int:
    source = int(context.dependency_outputs[TaskId("fetch")])
    multiplier = int(context.workflow_parameters["multiplier"])
    return source * multiplier


@workflow(
    id="examples.run-context",
    version="1",
    parameters=(WorkflowParameter(name="multiplier"),),
)
def demo() -> tuple[TaskHandle, ...]:
    return (fetch, transform)


runtime = WorkflowRuntime()
for handle in demo.task_handles():
    runtime.register(handle.handler_ref, handle.handler)

definition = demo.build()
run = runtime.run(definition, parameters={"multiplier": 3})
manifest = runtime.manifest(definition, run.run_id)

print(
    json.dumps(
        {
            "run_id": str(run.run_id),
            "status": run.status.value,
            "manifest_status": manifest.status,
        },
        sort_keys=True,
    )
)
