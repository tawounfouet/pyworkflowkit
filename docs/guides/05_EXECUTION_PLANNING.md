# 05 — Execution Planning

## What you will learn

You will see how a valid dependency graph becomes a deterministic execution plan and why
planning is a separate step from runtime execution.

## Mental model

```text
WorkflowDefinition
      ↓
Dependency graph
      ↓ validate
valid DAG
      ↓ plan
ExecutionPlan
      ↓
WorkflowRuntime
```

The DAG describes dependency structure. The execution plan turns that structure into an
ordered view that the runtime can execute safely.

## Example graph

```text
        prepare
       /       \
build_api   build_ui
       \       /
         publish
```

A valid layered plan is conceptually:

```text
Group 0  prepare
Group 1  build_api, build_ui
Group 2  publish
```

Tasks in the same group are structurally eligible for parallel execution, but the default
`WorkflowRuntime` remains the small sequential facade. Planning does not promise that a
specific executor will run tasks concurrently.

## Inspect planning from the CLI

```bash
pwk plan workflow:demo
```

Human output uses a Rich tree. Machine-facing automation should use:

```bash
pwk plan workflow:demo --json
```

## Determinism

For the same definition, planning should produce the same logical ordering. Deterministic
planning makes tests, debugging, manifests, and operational reasoning substantially easier.

## Validation vs planning vs execution

```text
validate
    Is the graph structurally legal?

plan
    In what deterministic order/groups can it execute?

run
    Execute it while respecting runtime state and evidence.
```

## Common mistakes

- treating the plan as current runtime state;
- assuming tasks in one plan group always run in parallel;
- expecting planning to execute handlers;
- relying on source-file declaration order instead of explicit dependencies.

## Exercises

1. Build a four-task fan-out/fan-in graph.
2. Inspect the human plan.
3. Inspect the JSON plan.
4. Change one dependency and compare the result.

## Related example

Canonical companion: [`examples/05_execution_plan.py`](../../examples/05_execution_plan.py).

## Related notebook

Canonical notebook: [`05 - Execution Planning.ipynb`](<../../notebooks/05 - Execution Planning.ipynb>).

## Next chapter

Continue with [06 — Workflow Runtime](06_WORKFLOW_RUNTIME.md).
