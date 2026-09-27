"""Canonical explicit task dependency example."""

from __future__ import annotations

import json

from pyworkflowkit import TaskHandle, task, workflow


@task
def fetch() -> int:
    return 21


@task(depends_on=(fetch,))
def transform() -> int:
    return 42


@task(depends_on=(transform,))
def publish() -> str:
    return "published"


@workflow(id="examples.dependencies", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (fetch, transform, publish)


definition = demo.build()

print(
    json.dumps(
        {
            str(task.task_id): [str(dependency) for dependency in task.depends_on]
            for task in definition.tasks
        },
        sort_keys=True,
    )
)
