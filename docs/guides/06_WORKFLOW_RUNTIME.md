# 06 — Workflow Runtime

## What you will learn

You will use `WorkflowRuntime` as the stable application facade and understand which
responsibilities belong to the runtime rather than to task handlers.

## Mental model

```text
WorkflowDefinition
      ↓
WorkflowRuntime
      ↓
validate / plan / execute
      ↓
WorkflowRun
      ↓
events / manifest / lineage
```

`WorkflowRuntime` is the small public composition facade. It wires runtime components
without requiring application code to construct the internal runner, metadata store,
planner, executor registry, and evidence services manually.

## Minimal execution

```python
from pyworkflowkit import WorkflowRuntime

runtime = WorkflowRuntime()

for handle in demo.task_handles():
    runtime.register(handle.handler_ref, handle.handler)

definition = demo.build()
run = runtime.run(definition)

print(run.run_id)
print(run.status)
```

## Runtime responsibilities

The runtime coordinates:

- workflow execution;
- handler lookup;
- task lifecycle;
- attempts and retries;
- metadata persistence;
- runtime events;
- final evidence.

The handler still owns its actual business work.

## Stable inspection methods

The public facade exposes:

```python
runtime.get_run(run_id)
runtime.events(run_id)
runtime.manifest(definition, run_id)
runtime.lineage(definition, run_id)
runtime.inspect_runtime(definition, run_id)
```

Recovery and reconciliation methods also exist for the advanced lifecycle and are covered
later in the learning path.

## Parameters

A workflow run may receive runtime values:

```python
run = runtime.run(
    definition,
    parameters={"source": "customers"},
)
```

Those values are run-specific. They do not mutate the workflow definition.

## Common mistakes

- making a handler manipulate runtime state directly;
- constructing internal runner services for ordinary sequential usage;
- treating a `WorkflowRun` as the workflow definition;
- persisting business secrets casually in workflow parameters.

## Exercises

1. Run the same definition twice and compare the two run IDs.
2. Reload a run with `get_run()`.
3. Print the event sequence.
4. Add one run parameter and read it from `RunContext` in the next chapter.

## Related example

Canonical companion: [`examples/06_runtime.py`](../../examples/06_runtime.py).

## Related notebook

Canonical notebook: [`06 - Workflow Runtime.ipynb`](<../../notebooks/06 - Workflow Runtime.ipynb>).

## Next chapter

Continue with [07 — RunContext and Data Flow](07_RUN_CONTEXT_AND_DATA_FLOW.md).
