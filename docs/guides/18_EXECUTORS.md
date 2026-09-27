# 18 — Executors

## What you will learn

You will understand the workload-execution boundary and the capabilities of the main
executor families.

## Core rule

```text
Executor executes
Runner orchestrates
State machine validates transitions
RetryEngine decides retries
MetadataStore persists
```

An executor does not decide whether the workflow should fail or which task should run next.

## Executor families

```text
LocalExecutor
    trusted Python, sequential

ThreadExecutor
    in-process parallel Python, soft timeout

ProcessExecutor
    isolated Python process, hard timeout/cancellation

AsyncExecutor
    awaitable workloads, cooperative cancellation

SubprocessExecutor
    external argv-based programs, shell=False
```

Advanced executors intentionally live outside the package-root beginner API.

## Handler contract

The stable handler boundary remains intentionally small:

```text
handler()
handler(context)
```

The executor normalizes the result into `TaskResult` or an execution failure.

## Subprocess security boundary

The subprocess adapter uses argv execution rather than shell parsing. The advanced security
policy can constrain executables, environment keys, working-directory roots, and captured
I/O size.

PyWorkflowKit does not claim to be an operating-system sandbox for untrusted code.

## Selecting an executor

Choose based on workload characteristics rather than fashion:

```text
simple trusted Python      → local
I/O with threads           → thread
isolation / hard kill      → process
native awaitables          → async
external CLI/program       → subprocess
```

## Common mistakes

- putting orchestration logic inside an executor;
- assuming all executors support the same timeout/cancellation strength;
- executing shell strings when argv semantics are available;
- treating executor isolation as full sandboxing.

## Exercises

1. Classify five workloads by executor type.
2. Compare thread vs process timeout semantics.
3. Explain why executor results must be normalized.
4. Identify which responsibilities stay outside the executor.

## Related example

Canonical companions:

- [`examples/15_concurrency.py`](../../examples/15_concurrency.py)
- [`examples/16_timeout.py`](../../examples/16_timeout.py)
- [`examples/17_cancellation.py`](../../examples/17_cancellation.py)
- [`examples/18_external_workload.py`](../../examples/18_external_workload.py)

## Related notebook

DX05 target: `14 - Executors.ipynb`.

## Next chapter

Continue with [19 — Plugins and Ecosystem](19_PLUGINS_AND_ECOSYSTEM.md).
