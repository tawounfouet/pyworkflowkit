"""Canonical concurrency-eligibility example through a public execution plan."""

from __future__ import annotations

import json

from pyworkflowkit import WorkflowRuntime
from pyworkflowkit.control_plane import WorkflowRuntimeProvider


workflow_definition: dict[str, object] = {
    "workflow_id": "examples.concurrency",
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
parallel_groups = [
    list(group.task_ids) for group in inspection.groups if len(group.task_ids) > 1
]

print(
    json.dumps(
        {
            "parallel_eligible_groups": parallel_groups,
            "scheduling_note": "plan eligibility does not itself dispatch concurrently",
        },
        sort_keys=True,
    )
)
