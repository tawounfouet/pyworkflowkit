# 01 — Installation and First Workflow

## What you will learn

You will install PyWorkflowKit, verify the CLI, define two dependent tasks, execute the
workflow, and inspect its terminal evidence.

## 1. Install

PyWorkflowKit requires Python 3.11 or newer.

```bash
python -m pip install pyworkflowkit
```

Confirm the installed command:

```bash
pwk version
```

`pwk` is canonical. `pyworkflowkit` and `pyworkflow` remain compatibility aliases.

## 2. Create the workflow

Create `workflow.py`:

```python
from pyworkflowkit import RunContext, TaskHandle, TaskId, task, workflow


@task
def fetch() -> int:
    return 21


@task(depends_on=(fetch,))
def transform(context: RunContext) -> int:
    return int(context.dependency_outputs[TaskId("fetch")]) * 2


@workflow(id="learning.first-workflow", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (fetch, transform)
```

Mental model:

```text
fetch
  ↓
transform
```

The decorators describe the workflow. They do not execute either function.

## 3. Execute it

Create `run.py`:

```python
from pyworkflowkit import WorkflowRuntime

from workflow import demo


runtime = WorkflowRuntime()

for handle in demo.task_handles():
    runtime.register(handle.handler_ref, handle.handler)

definition = demo.build()
run = runtime.run(definition)

print(run.status)
print(run.run_id)
```

Run:

```bash
python run.py
```

The default metadata backend is in-memory, which is appropriate for a first local run.

## 4. Inspect evidence in Python

Extend `run.py`:

```python
events = runtime.events(run.run_id)
manifest = runtime.manifest(definition, run.run_id)

print([event.event_type.value for event in events])
print(manifest.status)
```

This introduces the first evidence distinction:

```text
WorkflowRun
    current/final runtime state

RuntimeEvent
    ordered history of what happened

RunManifest
    portable terminal summary
```

## 5. Validate and plan from the CLI

For a module-level workflow target, the CLI reference format is:

```text
module:attribute
```

From the directory containing `workflow.py`:

```bash
pwk validate workflow:demo
pwk plan workflow:demo
```

Use `--json` when another program consumes the result:

```bash
pwk validate workflow:demo --json
pwk plan workflow:demo --json
```

## Object inspection

Try:

```python
print(type(demo))
print(demo.task_handles())
print(definition)
print(run)
```

The important observation is that the builder, definition, and run are different objects
with different responsibilities.

## Common mistakes

- forgetting to register task handlers before running a declarative workflow;
- passing a function result to `depends_on` instead of the task handle;
- expecting an in-memory run to survive a new process;
- parsing Rich human CLI output instead of using `--json`.

## Exercises

1. Change `fetch()` to return `50`.
2. Print the output received by `transform`.
3. Add a third task that depends on `transform`.
4. Run `pwk plan workflow:demo` before and after the new dependency.

## Related executable example

```text
examples/00_hello_world.py
```

Canonical companion: [`examples/01_tasks_and_handlers.py`](../../examples/01_tasks_and_handlers.py).

## Related notebook

DX05 will provide `01 - Hello Workflow.ipynb`.

## Next chapter

Continue with [02 — Tasks and Handlers](02_TASKS_AND_HANDLERS.md).
