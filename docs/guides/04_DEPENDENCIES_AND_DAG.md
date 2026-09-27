# 04 — Dependencies and DAG

## What you will learn

You will understand how task dependencies form a Directed Acyclic Graph (DAG), why cycles
are rejected, and how validation differs from execution.

## Mental model

A dependency:

```text
A → B
```

means:

```text
B depends on A
```

The graph is directed and must remain acyclic.

## Linear workflow

```python
from pyworkflowkit import RunContext, TaskHandle, TaskId, task, workflow


@task
def fetch() -> int:
    return 21


@task(depends_on=(fetch,))
def validate(context: RunContext) -> int:
    return int(context.dependency_outputs[TaskId("fetch")])


@task(depends_on=(validate,))
def transform(context: RunContext) -> int:
    return int(context.dependency_outputs[TaskId("validate")]) * 2


@workflow(id="learning.dag", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (fetch, validate, transform)
```

Graph:

```text
fetch
  ↓
validate
  ↓
transform
```

## Fan-out and fan-in

A DAG can express more than a list:

```text
        prepare
       /       \
build_api   build_ui
       \       /
         publish
```

That structure is why dependencies are explicit instead of being inferred from source-code
order.

## Validate the graph

```bash
pwk validate workflow:demo
```

Validation checks structural correctness before runtime execution. Invalid references,
self-dependencies, duplicate edges, and cycles belong to graph validation rather than task
execution.

## Inspect the plan

```bash
pwk plan workflow:demo
```

The Rich human view is designed for inspection. For deterministic machine consumption:

```bash
pwk plan workflow:demo --json
```

DAG and execution plan are related but distinct:

```text
DAG
    who depends on whom

ExecutionPlan
    deterministic executable ordering/grouping
```

## Common mistakes

- encoding dependencies only through function-call order;
- creating a cycle such as `A → B → C → A`;
- assuming source-code declaration order is the workflow plan;
- mixing runtime status into graph structure.

## Exercises

1. Build a fan-out workflow with two children of one root.
2. Add a fan-in task depending on both branches.
3. Compare `pwk plan` human and JSON output.
4. Intentionally create a cycle and observe validation failure.

## Related example

Canonical companions:

- [`examples/03_dependencies.py`](../../examples/03_dependencies.py)
- [`examples/04_dag.py`](../../examples/04_dag.py)

## Related notebook

Canonical notebook: [`04 - Dependencies and DAG.ipynb`](<../../notebooks/04 - Dependencies and DAG.ipynb>).

## Next chapter

Continue with [05 — Execution Planning](05_EXECUTION_PLANNING.md).
