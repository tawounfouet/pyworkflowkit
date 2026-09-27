# 08 — Failures and Retries

## What you will learn

You will configure task retries, distinguish an attempt failure from a terminal task
failure, and inspect retry evidence.

## Mental model

```text
TaskAttempt fails
      ↓
RetryPolicy + RetryEngine
      ↓
retry? ── yes ──→ another TaskAttempt
  │
  no
  ↓
TaskRun FAILED
      ↓
failure policy
      ↓
WorkflowRun may fail
```

An attempt failure is not automatically a terminal task failure.

## Retry once after a transient error

```python
from pyworkflowkit import BackoffStrategy, RetryPolicy, task


@task(
    retry_policy=RetryPolicy(
        max_attempts=2,
        backoff_strategy=BackoffStrategy.NONE,
        retryable_error_categories=frozenset({"RuntimeError"}),
    )
)
def unstable() -> str: ...
```

`max_attempts` includes the first attempt, so `2` means one retry is available.

## Retry evidence

After execution:

```python
events = runtime.events(run.run_id)
event_types = [event.event_type.value for event in events]

assert "TASK_RETRYING" in event_types
```

Retries remain part of the same task/run lineage. They do not create a new
`WorkflowRun`.

## Backoff strategies

The stable retry model supports:

```text
NONE
FIXED
LINEAR
EXPONENTIAL
```

Choose retry categories deliberately. Validation errors and deterministic programmer
errors should not be retried merely because retry infrastructure exists.

## Public error boundary

Applications that need one framework-level catch can use:

```python
from pyworkflowkit import PyWorkflowKitError

try:
    runtime.run(definition)
except PyWorkflowKitError as exc:
    print(type(exc).__name__, exc)
```

## Common mistakes

- setting `max_attempts=2` and expecting two retries;
- treating every exception as retryable;
- nesting PyWorkflowKit retries around an external system that already owns retry;
- assuming `TASK_RETRYING` means the `TaskRun` is terminally failed.

## Exercises

1. Write a handler that fails once and then succeeds.
2. Compare the event sequence with and without retry.
3. Use fixed backoff.
4. Make the final attempt fail and inspect the terminal state.

## Related example

Canonical companions:

- [`examples/08_failure.py`](../../examples/08_failure.py)
- [`examples/09_retry.py`](../../examples/09_retry.py)

The historical `examples/01_failure_and_retry.py` example remains available for compatibility.

## Related notebook

DX05 target: `08 - Failures and Retries.ipynb`.

## Next chapter

Continue with [09 — Events and Observability](09_EVENTS_AND_OBSERVABILITY.md).
