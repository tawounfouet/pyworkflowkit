# 03 — Workflow Definitions

## What you will learn

You will distinguish the lazy workflow builder from the immutable executable
`WorkflowDefinition`, and understand why workflow identity and version are explicit.

## Mental model

```text
@workflow function
       ↓
WorkflowBuilder
       ↓ build()
WorkflowDefinition
       ↓ run()
WorkflowRun
```

The definition says **what should be executed**. A run says **what is or was executed**.

## Minimal example

```python
from pyworkflowkit import TaskHandle, task, workflow


@task
def prepare() -> str:
    return "ready"


@workflow(id="learning.definition", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (prepare,)
```

Inspect the builder and materialized definition:

```python
print(demo)
definition = demo.build()
print(definition)
print(definition.workflow_id)
print(definition.version)
print(definition.tasks)
```

## Identity and version

A workflow identity is intentionally separate from its executable version:

```text
learning.definition / 1
learning.definition / 2
```

A meaningful behavior change should create a new version instead of silently mutating a
definition that has already been used.

## Immutability

Definition-time objects are designed to be stable inputs to validation and planning.
Runtime state such as `RUNNING`, timestamps, attempts, and outputs belongs to
`WorkflowRun` / task-run state, not to `WorkflowDefinition`.

## Validate before running

Save the workflow in `workflow.py` and run:

```bash
pwk validate workflow:demo
```

Machine-facing validation:

```bash
pwk validate workflow:demo --json
```

Validation failure occurs before a workload should be executed.

## Common mistakes

- using a workflow version as mutable metadata;
- storing runtime state in the definition;
- defining two tasks with the same logical ID;
- confusing the decorated builder with one concrete run.

## Exercises

1. Build the same workflow twice and inspect both definitions.
2. Change the workflow version from `1` to `2`.
3. Add another task and compare the resulting definition.
4. Validate both versions from the CLI.

## Related example

Canonical companion: [`examples/02_workflow_definitions.py`](../../examples/02_workflow_definitions.py).

## Related notebook

Canonical notebook: [`03 - Workflow Definitions.ipynb`](<../../notebooks/03 - Workflow Definitions.ipynb>).

## Next chapter

Continue with [04 — Dependencies and DAG](04_DEPENDENCIES_AND_DAG.md).
