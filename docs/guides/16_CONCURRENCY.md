# 16 — Concurrency

## What you will learn

You will understand how PyWorkflowKit moves from a deterministic DAG to bounded concurrent
execution without giving workers ownership of runtime state.

## Mental model

```text
READY tasks
    ↓
capacity accounting
    ↓
concurrent executor
    ↓
completion queue
    ↓
coordinator
    ↓
state transitions
```

The coordinator remains the authority for workflow/task state. Worker execution produces
completion information; workers do not independently mutate the runtime state machine.

## Fan-out / fan-in

```text
        prepare
       /       \
build_api   build_ui
       \       /
         publish
```

The two middle tasks may execute concurrently when capacity and executor capabilities allow
it. `publish` still waits for both dependencies.

## Advanced API boundary

The small public `WorkflowRuntime` facade remains sequential/local. Concurrency is an
advanced composition using `ConcurrentRunner` plus a concurrent executor such as
`ThreadExecutor`.

This separation keeps first-use behavior simple while exposing explicit concurrency when
the application actually needs it.

## Capacity

Concurrency is bounded rather than “spawn everything”:

```text
global limit
    +
executor max_concurrency
    ↓
effective capacity
```

## Failure behavior

Under fail-fast semantics, a terminal failure stops new dispatch. Work already running is
allowed to reach a normalized completion according to the executor/cancellation contract.

## Common mistakes

- assuming a plan group guarantees parallel execution;
- letting worker threads/processes mutate domain state;
- setting unbounded concurrency;
- ignoring executor capability differences.

## Exercises

1. Draw a fan-out/fan-in DAG.
2. Identify which tasks can run concurrently.
3. Compare sequential and concurrent execution semantics.
4. Explain why state transitions stay coordinator-owned.

## Related example

DX04 target: `examples/15_concurrency.py`.

## Related notebook

DX05 target: `13 - Concurrency.ipynb`.

## Next chapter

Continue with [17 — Timeouts and Cancellation](17_TIMEOUTS_AND_CANCELLATION.md).
