# Failures and Retries

Retries are declared on the task definition through `RetryPolicy`.

A complete executable example is:

```text
examples/01_failure_and_retry.py
```

## Retry once after a transient failure

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

`max_attempts` includes the initial attempt. A value of `2` therefore permits one
retry.

The error category used by the local Python execution path is based on the exception type.
The example deliberately raises `RuntimeError` once, then succeeds.

## Observe retry evidence

After a successful run:

```python
events = runtime.events(run.run_id)
event_types = [event.event_type.value for event in events]

assert "TASK_RETRYING" in event_types
```

Retries do not create a new workflow run. They are attempts associated with the existing
task execution lineage.

## Handle terminal workflow failures

Application code should catch the stable package exception boundary when it wants one
generic PyWorkflowKit error handler:

```python
from pyworkflowkit import PyWorkflowKitError

try:
    runtime.run(definition)
except PyWorkflowKitError as exc:
    print(type(exc).__name__, exc)
```

Use more specific internal exception classes only when you deliberately accept a narrower
compatibility boundary than the package facade.

## Backoff

`RetryPolicy` supports `NONE`, `FIXED`, `LINEAR`, and `EXPONENTIAL` backoff
strategies. Keep retry ownership in one runtime when an external workload has its own
retry mechanism; the external-workload integration contract makes that ownership
explicit.
