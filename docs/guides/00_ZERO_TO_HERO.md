# 00 — Zero to Hero

## What you will learn

This chapter explains how to learn PyWorkflowKit without starting from its internals.

The core idea is simple:

```text
ordinary Python functions
        ↓
explicit tasks
        ↓
workflow definition
        ↓
dependency graph
        ↓
validated execution plan
        ↓
runtime execution
        ↓
events + manifest + persistence
```

PyWorkflowKit adds workflow-runtime guarantees while remaining an embeddable Python library.

## Mental model

A useful first distinction is:

```text
definition-time
    what should run

runtime
    what is running / what ran

evidence
    what happened
```

The main public concepts map naturally to that model:

```text
TaskHandle / TaskDefinition
        ↓
WorkflowDefinition
        ↓
WorkflowRuntime
        ↓
WorkflowRun
        ↓
RuntimeEvent / RunManifest
```

You do not need to understand SQLAlchemy, internal repositories, state-machine
implementation details, or executor internals to build your first workflow.

## The learning workflow

The first chapters evolve one small workflow:

```text
fetch
  ↓
transform
```

Then the path grows toward:

```text
fetch
  ↓
validate
  ↓
transform
  ↓
publish
```

That progression is deliberate: it makes dependencies, data flow, planning, retries,
events, persistence, and CLI inspection visible one concept at a time.

## First public-API shape

```python
from pyworkflowkit import TaskHandle, WorkflowRuntime, task, workflow


@task
def hello() -> str:
    return "hello"


@workflow(id="learning.hello", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (hello,)


runtime = WorkflowRuntime()
for handle in demo.task_handles():
    runtime.register(handle.handler_ref, handle.handler)

definition = demo.build()
run = runtime.run(definition)

print(run.status)
```

Decoration is lazy: declaring the task and workflow does not execute the workload.

## CLI mental model

The canonical CLI command is `pwk`.

```text
pwk validate
      ↓
pwk plan
      ↓
pwk run
      ↓
pwk inspect
      ↓
pwk events
      ↓
pwk manifest
```

Human output uses Rich rendering where useful. Automation should use `--json`.

## Common mistakes

- treating `@task` decoration as execution;
- importing internal modules when the package facade already exposes the concept;
- confusing a workflow definition with one concrete workflow run;
- using the human Rich output as a machine contract;
- assuming PyWorkflowKit schedules workflows by itself.

## Exercise

Before continuing, explain in your own words the difference between:

```text
WorkflowDefinition
WorkflowRun
RunManifest
```

## Related executable example

Current repository reference:

```text
examples/00_hello_world.py
```

The complete canonical example set is delivered by DX04.

## Related notebook

The notebook learning path is delivered by DX05.

## Next chapter

Continue with [01 — Installation and First Workflow](01_INSTALLATION_AND_FIRST_WORKFLOW.md).
