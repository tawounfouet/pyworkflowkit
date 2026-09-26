# Timeout semantics

M31 completes the 0.4 execution-control model with explicit timeout semantics.

## Task contract

A task carries two timeout values:

```text
timeout_seconds
timeout_mode
```

`TimeoutMode` is one of:

```text
NONE
SOFT
HARD
```

For backward compatibility, an existing task that supplies `timeout_seconds` without an explicit mode is normalized to `SOFT`.

An explicit `SOFT` or `HARD` mode requires `timeout_seconds`.

## Capability validation

The runtime validates requested task semantics against `ExecutorCapabilities.timeout` before creating a WorkflowRun.

```text
requested NONE → always valid
requested SOFT → executor SOFT or HARD
requested HARD → executor HARD only
```

`LocalExecutor` declares `NONE`, so any timeout request is rejected.

`ThreadExecutor` declares `SOFT`, so hard timeout requests are rejected.

## Soft timeout

A ThreadExecutor soft timeout is a **logical runtime timeout**, not thread termination.

```text
TaskAttempt RUNNING
        ↓ deadline
TaskAttempt FAILED
error_type     = ExecutionTimeoutError
error_category = timeout
        ↓
RetryEngine
```

No `TIMED_OUT` status is introduced. This follows the runtime model: timeout is represented as a failed attempt with timeout error evidence.

## Physical worker lifecycle

When a soft timeout occurs, the Python worker thread may still be running.

PyWorkflowKit therefore keeps the physical execution handle and its capacity lease until the thread actually finishes.

Its late completion is not allowed to overwrite the already-recorded timeout outcome.

```text
logical attempt FAILED(timeout)
        │
        ├── runtime state is final for that attempt
        │
        └── thread may still finish later
                    ↓
             late completion ignored
                    ↓
             capacity lease released
```

## Retry integration

`ExecutionTimeoutError` extends `TaskExecutionError`, so the existing `RetryEngine` handles timeout failures without a parallel retry subsystem.

A timeout can be filtered explicitly with:

```python
RetryPolicy(
    max_attempts=2,
    retryable_error_categories=frozenset({"timeout"}),
)
```

For a soft timeout, a retry of the same TaskRun is not submitted until the timed-out physical thread has returned. This prevents overlapping physical executions of two attempts for the same task.

## HARD timeout

M31 defines and validates the `HARD` semantic level but ThreadExecutor does not implement it.

Hard timeout requires an executor capable of stronger termination semantics. The roadmap introduces ProcessExecutor in M32, where stronger process-level termination can be implemented without pretending Python threads are killable.

## Interaction with cancellation

Timeout and cancellation remain distinct:

```text
timeout
    = attempt exceeded declared execution deadline

cancellation
    = workflow stop requested externally or by KeyboardInterrupt
```

A cancellation request can still occur while a soft-timed-out physical thread is winding down. The logical timeout result remains immutable; the coordinator only waits for physical cleanup before completing cancellation.

## Boundary

M31 does not introduce:

- hard thread killing;
- a `TIMED_OUT` lifecycle status;
- non-blocking retry scheduling;
- process termination;
- async cancellation.

Those concerns belong to later executor and recovery milestones.
