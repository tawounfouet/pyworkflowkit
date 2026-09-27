# 07 — RunContext and Data Flow

## What you will learn

You will pass data between tasks through dependency outputs and access run-specific values
through the immutable `RunContext`.

## Mental model

```text
upstream TaskResult/output
          ↓
dependency_outputs
          ↓
RunContext
          ↓
downstream handler
```

`RunContext` is read-only execution context. It identifies the active workflow run, task
run, attempt, task, parameters, and dependency outputs.

## Dependency data flow

```python
from pyworkflowkit import RunContext, TaskId, task


@task
def fetch() -> int:
    return 21


@task(depends_on=(fetch,))
def transform(context: RunContext) -> int:
    value = context.dependency_outputs[TaskId("fetch")]
    return int(value) * 2
```

The dependency declaration controls readiness. The context supplies the completed upstream
output.

## Workflow parameters

Start the run with parameters:

```python
run = runtime.run(
    definition,
    parameters={"multiplier": 3},
)
```

Read them in a handler:

```python
@task(depends_on=(fetch,))
def transform(context: RunContext) -> int:
    source = int(context.dependency_outputs[TaskId("fetch")])
    multiplier = int(context.workflow_parameters["multiplier"])
    return source * multiplier
```

## Useful context fields

```text
workflow_run_id
task_run_id
attempt_id
task_id
attempt_number
workflow_parameters
dependency_outputs
```

The mappings are frozen for the handler boundary so a workload cannot accidentally mutate
the runtime's context container.

## Zero-argument handlers

A task that needs no context may remain simple:

```python
@task
def prepare() -> str:
    return "ready"
```

PyWorkflowKit deliberately supports the straightforward `handler()` and
`handler(context)` styles rather than broad magical argument injection.

## Common mistakes

- reading an output from a task that is not a declared dependency;
- mutating context mappings;
- using global variables as hidden cross-task state;
- confusing workflow parameters with definition metadata.

## Exercises

1. Pass two workflow parameters to a run.
2. Use an upstream output and one parameter in a downstream task.
3. Print `attempt_number`.
4. Compare two runs with different parameter values.

## Related example

Canonical companion: [`examples/07_run_context.py`](../../examples/07_run_context.py).

## Related notebook

DX05 target: `07 - RunContext and Data Flow.ipynb`.

## Next chapter

Continue with [08 — Failures and Retries](08_FAILURES_AND_RETRIES.md).
