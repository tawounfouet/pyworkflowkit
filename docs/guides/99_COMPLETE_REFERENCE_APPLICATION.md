# 99 — Complete Reference Application

## Goal

This final guide combines the main concepts into one small data-processing workflow without
turning PyWorkflowKit into an ETL framework.

The workload logic is illustrative; PyWorkflowKit owns only the graph and execution
mechanics.

## Workflow

```text
fetch
  ↓
validate
  ↓
transform
  ↓
publish
```

## Definition

```python
from pyworkflowkit import (
    BackoffStrategy,
    RetryPolicy,
    RunContext,
    TaskHandle,
    TaskId,
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


@workflow(id="reference.data-pipeline", version="1")
def pipeline() -> tuple[TaskHandle, ...]:
    return (fetch, validate, transform, publish)
```

## Durable runtime

```python
from pathlib import Path

from pyworkflowkit import RuntimeSettings, WorkflowRuntime


settings = RuntimeSettings.load(
    overrides={
        "runtime": {"workspace": Path(".pyworkflow-reference")},
        "metadata": {
            "backend": "sqlite",
            "sqlite_path": "runtime.sqlite3",
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

print(run.status)
print(len(events))
print(manifest.status)
print(lineage)
```

## CLI journey

Save the definition in an importable module and use:

```bash
pwk validate reference_workflow:pipeline
pwk plan reference_workflow:pipeline
pwk run reference_workflow:pipeline --config pyworkflowkit.toml --json
pwk inspect <RUN_ID> --config pyworkflowkit.toml
pwk events <RUN_ID> --config pyworkflowkit.toml
pwk manifest reference_workflow:pipeline <RUN_ID> --config pyworkflowkit.toml
```

## What this application demonstrates

```text
task declaration
workflow definition
dependency graph
deterministic planning
RunContext data flow
retry policy
durable metadata
runtime events
manifest
lineage
CLI operation
```

## What it deliberately does not demonstrate

```text
scheduler
Web UI
IAM
distributed worker fleet
business-specific ingestion lifecycle
platform governance
```

Those remain outside the PyWorkflowKit core product boundary.

## Next

DX04 turns these teaching concepts into the complete canonical executable example set.
DX05 then adds interactive notebooks, and DX06 qualifies consistency across every surface.
