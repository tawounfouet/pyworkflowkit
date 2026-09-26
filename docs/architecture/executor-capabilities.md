# Executor capabilities

M25 introduces an explicit capability contract before PyWorkflowKit introduces
concurrent execution.

An Executor declares:

- whether it supports parallel execution;
- its timeout strength: `none`, `soft`, or `hard`;
- its cancellation strength: `none`, `cooperative`, or `hard`;
- its intrinsic `max_concurrency`.

The runtime must inspect these values rather than infer behavior from an executor
name or implementation type.

## Conservative baseline

`LocalExecutor` remains:

```text
supports_parallelism = false
timeout              = none
cancellation         = none
max_concurrency       = 1
```

M25 does not add threads, asynchronous dispatch, timeout enforcement, or
cancellation handling. Those behaviors arrive in later milestones.

## Compatibility

The pre-M25 boolean views remain available:

```text
supports_hard_timeout
supports_hard_cancellation
```

They are derived from the stronger enum-based capability values and are not
independent state.

## Invariant

A non-parallel executor must declare `max_concurrency=1`.

The later M26 CapacityManager will combine executor-declared intrinsic capacity
with runtime-level global and per-executor slot limits.
