"""Canonical DAG-shape example using public task definitions."""

from __future__ import annotations

import json

from pyworkflowkit._compat.v1_root import TaskHandle, task, workflow


@task
def prepare() -> str:
    return "ready"


@task(depends_on=(prepare,))
def build_api() -> str:
    return "api"


@task(depends_on=(prepare,))
def build_ui() -> str:
    return "ui"


@task(depends_on=(build_api, build_ui))
def publish() -> str:
    return "published"


@workflow(id="examples.dag", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (prepare, build_api, build_ui, publish)


definition = demo.build()
task_ids = {task.task_id for task in definition.tasks}
depended_on = {dependency for task in definition.tasks for dependency in task.depends_on}

print(
    json.dumps(
        {
            "leaves": sorted(str(task_id) for task_id in task_ids - depended_on),
            "roots": sorted(str(task.task_id) for task in definition.tasks if not task.depends_on),
            "tasks": sorted(str(task_id) for task_id in task_ids),
        },
        sort_keys=True,
    )
)
