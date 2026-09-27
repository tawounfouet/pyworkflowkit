# Getting Started

This guide is the shortest supported path from installation to a successful PyWorkflowKit run.

## 1. Install

PyWorkflowKit requires Python 3.11 or newer.

```bash
python -m pip install pyworkflowkit
```

Confirm the installation:

```bash
pwk version
```

`pwk` is the canonical CLI command. `pyworkflowkit` and `pyworkflow` remain supported compatibility aliases.

## 2. Define tasks and a workflow

Create `workflow.py`:

```python
from pyworkflowkit import RunContext, TaskHandle, TaskId, task, workflow


@task
def fetch() -> int:
    return 21


@task(depends_on=(fetch,))
def transform(context: RunContext) -> int:
    return int(context.dependency_outputs[TaskId("fetch")]) * 2


@workflow(id="getting-started", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (fetch, transform)
```

Decorating a function does not execute it. `@task` records task metadata and `@workflow`
creates a lazy `WorkflowBuilder`.

## 3. Execute through the public runtime

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

The default metadata backend is in-memory. It is appropriate for local experiments and
tests where durability across processes is not required.

## 4. Inspect durable runtime evidence

For the current runtime instance:

```python
events = runtime.events(run.run_id)
manifest = runtime.manifest(definition, run.run_id)

print(len(events))
print(manifest.status)
```

A complete executable version of this flow is:

```text
examples/00_hello_world.py
```

Run it with:

```bash
python examples/00_hello_world.py
```

## 5. Use the CLI

For validation, planning, execution, and inspection from separate commands, use a durable
metadata backend and follow [CLI Workflow](cli-workflow.md).

## Next

- [Failures and Retries](failures-and-retries.md)
- [Persistence and Evidence](persistence-and-evidence.md)
- [CLI Workflow](cli-workflow.md)
- [Plugin Authoring](plugin-authoring.md)
- [Troubleshooting](troubleshooting.md)

## Boundary to remember

The recommended 1.0 authoring path starts from:

```text
pyworkflowkit
pyworkflowkit.ecosystem
```

Advanced implementation modules may exist, but they are not required for the first-use
workflow documented here.
