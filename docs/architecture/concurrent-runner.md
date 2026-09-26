# Concurrent Runner

M29 assembles the concurrency foundations introduced in M25–M28.

The governing rule is:

```text
workers execute
coordinator transitions state
```

## Coordinator ownership

`ConcurrentRunner` is the only component that:

- marks TaskRuns READY;
- starts TaskRuns and creates TaskAttempts;
- applies attempt success/failure;
- evaluates RetryPolicy;
- persists runtime transitions and events;
- advances DAG readiness;
- applies FAIL_FAST;
- finalizes WorkflowRun state.

Worker threads only execute handlers and publish `AttemptCompletion` values.

## Dispatch loop

```text
scan PENDING tasks
      ↓
mark newly eligible tasks READY
      ↓
acquire CapacityLease
      ↓
READY → RUNNING
      ↓
ThreadExecutor.submit()
      ↓
workers execute in parallel
      ↓
CompletionQueue
      ↓
coordinator consumes one completion
      ↓
release CapacityLease
      ↓
persist success/failure/retry
      ↓
re-evaluate readiness
```

This keeps runtime-state authority serialized even though workload execution is
parallel.

## Capacity

The coordinator uses `CapacityManager` before every initial attempt and retry attempt.

Effective concurrency is bounded by both:

```text
global_limit
and
ThreadExecutor.capabilities.max_concurrency
```

An optional executor-level limit can reduce the intrinsic executor capacity further.

## Fan-out / fan-in

For:

```text
        A
     ┌──┴──┐
     ▼     ▼
     B     C
     └──┬──┘
        ▼
        D
```

the coordinator may dispatch B and C concurrently after A succeeds. D becomes READY
only after both B and C are persisted as SUCCEEDED.

## Duplicate-ready protection

Only the coordinator evaluates readiness and changes `PENDING → READY → RUNNING`.
A TaskRun that is already READY or RUNNING is therefore not rediscovered as newly
ready.

Each physical attempt also owns one CapacityLease and one ExecutionHandle.

## FAIL_FAST with running siblings

When one TaskRun becomes terminally FAILED:

- the coordinator stops dispatching newly ready work;
- PENDING/READY descendants become SKIPPED with `DEPENDENCY_FAILED`;
- other PENDING/READY tasks become SKIPPED with `FAIL_FAST_ABORT`;
- TaskRuns that were already RUNNING are allowed to reach a terminal state;
- no hard cancellation is attempted in M29.

A later failure from an already-running sibling records TASK_FAILED but does not
attempt a second WorkflowRun transition to FAILED.

This preserves the runtime-lifecycle rule that running work is allowed to finish until
M30 introduces explicit cancellation semantics.

## Retry

Retry decisions remain coordinator-owned. Backoff still uses the existing synchronous
Sleeper contract. This can temporarily pause completion processing and is intentionally
not redesigned in M29.

M40 later introduces non-blocking retry eligibility.

## Boundaries

M29 does not implement:

- cancellation requests;
- hard or cooperative cancellation of running threads;
- terminal timeout failure;
- non-blocking retry scheduling;
- process or async execution.

Those belong to M30, M31, M40, and later executor milestones.
