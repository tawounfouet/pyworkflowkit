# Capacity model

M26 introduces bounded slot accounting before PyWorkflowKit introduces concurrent
dispatch.

`CapacityManager` owns only capacity accounting. It does not select tasks, execute
handlers, transition runtime state, or create threads.

## Inputs

The manager receives:

- a global slot limit;
- one `ExecutorCapabilities` contract per executor;
- optional runtime-level per-executor limits.

The effective executor limit is:

```text
min(configured per-executor limit, executor.max_concurrency)
```

This means runtime configuration may reduce intrinsic executor capacity but cannot
increase it.

## Reservation identity

Each active slot is owned by one `TaskAttemptId`.

```text
TaskAttemptId
    ↓
CapacityLease
    ↓
executor_key
```

A duplicate reservation for the same attempt is an invariant violation.

## Acquisition

`try_acquire()` returns:

- `CapacityLease` when both global and executor capacity are available;
- `None` when capacity is currently saturated.

Saturation is normal control flow, not an exception.

Unknown executors, duplicate active attempts, invalid limits, and invalid releases are
errors.

## Thread safety

Capacity accounting is guarded by an internal lock because M28/M29 will introduce
multiple workers and concurrent completion signals.

## Boundary

M26 does not introduce:

- task dispatch;
- execution handles;
- completion queues;
- thread pools;
- cancellation;
- timeout enforcement.

Those concerns begin with M27 and later milestones.
