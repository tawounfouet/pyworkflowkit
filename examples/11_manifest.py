"""Canonical RunManifest evidence example."""

from __future__ import annotations

import json

from pyworkflowkit._compat.v1_root import TaskHandle, WorkflowRuntime, task, workflow


@task
def produce() -> dict[str, int]:
    return {"rows": 3}


@workflow(id="examples.manifest", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (produce,)


runtime = WorkflowRuntime()
runtime.register(produce.handler_ref, produce.handler)

definition = demo.build()
run = runtime.run(definition)
manifest = runtime.manifest(definition, run.run_id)

print(
    json.dumps(
        {
            "run_id": str(manifest.run_id),
            "status": manifest.status,
            "workflow_id": str(manifest.workflow_id),
        },
        sort_keys=True,
    )
)
