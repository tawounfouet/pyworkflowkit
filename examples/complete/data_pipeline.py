"""Complete canonical data-pipeline example for the DX04 learning path."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from pyworkflowkit import (
    BackoffStrategy,
    RetryPolicy,
    RunContext,
    RuntimeSettings,
    TaskHandle,
    TaskId,
    WorkflowRuntime,
    task,
    workflow,
)


@task(
    retry_policy=RetryPolicy(
        max_attempts=2,
        backoff_strategy=BackoffStrategy.NONE,
        retryable_error_categories=frozenset({"ConnectionError"}),
    )
)
def fetch() -> list[int]:
    return [1, 2, 3]


@task(depends_on=(fetch,))
def validate(context: RunContext) -> list[int]:
    values = context.dependency_outputs[TaskId("fetch")]
    return [int(value) for value in values]


@task(depends_on=(validate,))
def transform(context: RunContext) -> list[int]:
    values = context.dependency_outputs[TaskId("validate")]
    return [int(value) * 10 for value in values]


@task(depends_on=(transform,))
def publish(context: RunContext) -> int:
    values = context.dependency_outputs[TaskId("transform")]
    return len(values)


@workflow(id="examples.complete.data-pipeline", version="1")
def pipeline() -> tuple[TaskHandle, ...]:
    return (fetch, validate, transform, publish)


with TemporaryDirectory() as directory:
    workspace = Path(directory)
    settings = RuntimeSettings.load(
        overrides={
            "runtime": {"workspace": workspace},
            "metadata": {
                "backend": "sqlite",
                "sqlite_path": "runtime.sqlite3",
                "sqlite_wal": False,
            },
        }
    )

    runtime = WorkflowRuntime(settings)
    for handle in pipeline.task_handles():
        runtime.register(handle.handler_ref, handle.handler)

    definition = pipeline.build()
    run = runtime.run(definition)
    events = runtime.events(run.run_id)
    manifest = runtime.manifest(definition, run.run_id)
    lineage = runtime.lineage(definition, run.run_id)

    print(
        json.dumps(
            {
                "event_count": len(events),
                "lineage_task_count": len(lineage.tasks),
                "manifest_status": manifest.status,
                "run_status": run.status.value,
                "task_count": len(definition.tasks),
            },
            sort_keys=True,
        )
    )
