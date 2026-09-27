"""Canonical deterministic execution-plan example through the public provider contract."""

from __future__ import annotations

import json

from pyworkflowkit import WorkflowRuntime
from pyworkflowkit.control_plane import WorkflowRuntimeProvider

workflow_definition: dict[str, object] = {
    "workflow_id": "examples.execution-plan",
    "version": "1",
    "tasks": [
        {"task_id": "prepare", "handler_ref": "handlers:prepare"},
        {
            "task_id": "build_api",
            "handler_ref": "handlers:build_api",
            "depends_on": ["prepare"],
        },
        {
            "task_id": "build_ui",
            "handler_ref": "handlers:build_ui",
            "depends_on": ["prepare"],
        },
        {
            "task_id": "publish",
            "handler_ref": "handlers:publish",
            "depends_on": ["build_api", "build_ui"],
        },
    ],
}

inspection = WorkflowRuntimeProvider(WorkflowRuntime()).inspect_workflow(workflow_definition)

print(
    json.dumps(
        {
            "groups": [
                {"index": group.index, "tasks": list(group.task_ids)}
                for group in inspection.groups
            ],
            "task_order": list(inspection.task_order),
        },
        sort_keys=True,
    )
)
