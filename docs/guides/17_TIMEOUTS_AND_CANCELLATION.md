# 17 — Timeouts and Cancellation

## What you will learn

You will distinguish timeout intent from executor capability and understand the difference
between soft, cooperative, and hard interruption.

## Timeout modes

The public domain exposes:

```python
from pyworkflowkit import TaskDefinition, TaskId, TimeoutMode
```

A task may declare timeout semantics through `timeout_seconds` and `timeout_mode`.

Conceptually:

```text
NONE
SOFT
HARD
```

The requested mode must be compatible with the selected executor.

## Why executor capability matters

A Python thread cannot be safely force-killed by the runtime. `ThreadExecutor` therefore
supports soft timeout semantics rather than pretending to provide hard termination.

A process-owned workload can support stronger termination semantics. The runtime models
those differences explicitly.

## Cancellation capability

Executors advertise cancellation as:

```text
none
cooperative
hard
```

Examples:

- asyncio cancellation is cooperative;
- isolated owned processes can support hard termination;
- plain local execution may expose no independent cancellation mechanism.

## Retry interaction

A timeout is normalized into the existing failure/retry model. Timeout does not create a
second, special workflow engine.

```text
timeout
  ↓
normalized execution failure
  ↓
RetryEngine
  ↓
retry or terminal failure
```

## Common mistakes

- requesting HARD timeout from an executor that only supports SOFT;
- assuming a timed-out thread stopped physically;
- retrying before the previous physical execution has actually cleaned up;
- confusing workflow cancellation with task timeout.

## Exercises

1. Compare soft and hard timeout semantics.
2. Identify which executor type can own hard process termination.
3. Explain why cooperative asyncio cancellation is not hard termination.
4. Trace a timeout through the retry engine.

## Related example

DX04 targets: `examples/16_timeout.py` and `examples/17_cancellation.py`.

## Next chapter

Continue with [18 — Executors](18_EXECUTORS.md).
