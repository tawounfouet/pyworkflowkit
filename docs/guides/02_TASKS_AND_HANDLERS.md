# 02 — Tasks and Handlers

## What you will learn

You will understand what a PyWorkflowKit task represents, how `@task` wraps a trusted
Python callable, what a handler reference is, and why declaration stays separate from
execution.

## Mental model

```text
Python callable
    ↓ decorated as
TaskHandle
    ↓ materialized in
TaskDefinition
    ↓ executed by
Executor
```

A task is a node in the workflow graph. The handler is the Python workload associated with
that node.

## Minimal example

```python
from pyworkflowkit import task


@task
def fetch() -> dict[str, int]:
    return {"rows": 10}
```

At import time, `fetch` is declared as a task handle. The workload body has not run.

## Inspect the handle

```python
print(fetch)
print(fetch.handler)
print(fetch.handler_ref)
```

The handler reference gives the runtime a stable way to associate a planned task with the
registered callable.

## Registering handlers

`WorkflowRuntime` deliberately keeps registration explicit:

```python
from pyworkflowkit import WorkflowRuntime

runtime = WorkflowRuntime()
runtime.register(fetch.handler_ref, fetch.handler)
```

The runtime owns orchestration. Your function continues to own its business logic.

## Returning values

A handler may return an ordinary supported value:

```python
@task
def count_rows() -> int:
    return 42
```

Downstream tasks can access dependency outputs through `RunContext`.

For richer runtime evidence, advanced handlers may return `TaskResult`, which is covered
later in the learning path.

## Task dependencies

Dependencies are declared on the task:

```python
from pyworkflowkit import RunContext, TaskId, task


@task
def fetch() -> int:
    return 21


@task(depends_on=(fetch,))
def transform(context: RunContext) -> int:
    return int(context.dependency_outputs[TaskId("fetch")]) * 2
```

This is not merely a Python call sequence. It becomes graph structure.

## CLI equivalent

Tasks are normally observed through their containing workflow:

```bash
pwk validate workflow:demo
pwk plan workflow:demo
```

## Common mistakes

- calling the underlying handler during declaration to manufacture a dependency;
- hiding orchestration inside one giant task;
- assuming the runtime should understand the business semantics of the handler;
- placing scheduler or platform concerns inside a task definition.

## Exercises

1. Create three independent tasks.
2. Give each one a small deterministic return value.
3. Build one workflow containing all three.
4. Inspect the resulting plan before adding dependencies.

## Related example

Canonical companion: [`examples/01_tasks_and_handlers.py`](../../examples/01_tasks_and_handlers.py).

## Related notebook

Canonical notebook: [`02 - Tasks and Handlers.ipynb`](<../../notebooks/02 - Tasks and Handlers.ipynb>).

## Next chapter

Continue with [03 — Workflow Definitions](03_WORKFLOW_DEFINITIONS.md).
