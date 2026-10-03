"""Canonical control-plane provider example."""

from __future__ import annotations

import json

from pyworkflowkit._compat.v1_root import WorkflowRuntime
from pyworkflowkit.control_plane import WorkflowRuntimeProvider

runtime = WorkflowRuntime()
runtime.register("handlers:hello", lambda: "hello")

provider = WorkflowRuntimeProvider(runtime, provider_name="example.control-plane")
workflow_definition: dict[str, object] = {
    "workflow_id": "examples.control-plane",
    "version": "1",
    "tasks": [
        {
            "task_id": "hello",
            "handler_ref": "handlers:hello",
        }
    ],
}

validation = provider.validate_workflow(workflow_definition)
run = provider.execute_workflow(workflow_definition)
capabilities = provider.inspect_capabilities()

print(
    json.dumps(
        {
            "provider": capabilities.provider_name,
            "run_status": run.status,
            "valid": validation.valid,
        },
        sort_keys=True,
    )
)
