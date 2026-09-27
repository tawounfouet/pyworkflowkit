"""Canonical immutable WorkflowDefinition example."""

from __future__ import annotations

import json

from pyworkflowkit import TaskHandle, task, workflow


@task
def prepare() -> str:
    return "ready"


@task(depends_on=(prepare,))
def publish() -> str:
    return "published"


@workflow(
    id="examples.workflow-definition",
    version="1",
    description="Small immutable workflow definition.",
)
def demo() -> tuple[TaskHandle, ...]:
    return (prepare, publish)


definition = demo.build()

print(
    json.dumps(
        {
            "task_ids": [str(task.task_id) for task in definition.tasks],
            "version": definition.version,
            "workflow_id": str(definition.workflow_id),
        },
        sort_keys=True,
    )
)
