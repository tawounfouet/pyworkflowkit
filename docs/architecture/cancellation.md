# Cancellation

M30 introduces explicit workflow cancellation for the concurrent runtime.

The governing rule remains capability-aware:

```text
cancel requested
      ↓
stop new dispatch
      ↓
PENDING / READY → CANCELLED
      ↓
RUNNING attempts
      ↓
executor capability decides what is possible
```

## CancellationController

`CancellationController` is a thread-safe, first-writer-wins signal.

```python
controller = CancellationController()
controller.request(reason="user_requested")

runner.run(
    workflow,
    cancellation=controller,
)
```

The first accepted reason is preserved deterministically.

## Undispatched tasks

When the coordinator observes cancellation:

```text
PENDING → CANCELLED
READY   → CANCELLED
```

No new tasks or retry attempts are dispatched after the request is observed.

A TaskRun waiting between retry attempts is also cancelled because no physical attempt is currently running.

## Running attempts

`ThreadExecutor` still declares:

```text
cancellation = none
```

Therefore M30 does not pretend that Python threads can be safely hard-cancelled.

Already running attempts are allowed to reach a natural terminal state:

```text
RUNNING attempt succeeds
    → TaskRun SUCCEEDED

RUNNING attempt fails
    → TaskRun FAILED
```

The coordinator drains those completions before finalizing the WorkflowRun.

## Workflow result

An explicit cancellation request finalizes the run as:

```text
WorkflowRun → CANCELLED
```

The `WORKFLOW_CANCELLED` event carries the cancellation reason and the number of undispatched tasks normalized to CANCELLED.

The V0 event model does not define `TASK_CANCELLED`. M30 therefore persists cancelled TaskRun state directly and emits the workflow-level cancellation fact without inventing a new task event type.

## Retry interaction

Once cancellation is requested, a failed running attempt does not create another retry attempt even when its RetryPolicy would otherwise allow one.

```text
cancel requested
    ≠
new work scheduled later
```

## KeyboardInterrupt

A `KeyboardInterrupt` observed by the coordinator is normalized into:

```text
reason = "keyboard_interrupt"
```

and follows the same graceful cancellation path.

## Graceful shutdown

For ThreadExecutor, graceful cancellation means:

1. stop dispatching new work;
2. cancel PENDING/READY work;
3. allow already-running threads to finish naturally;
4. consume their completions;
5. persist terminal task state;
6. finalize the WorkflowRun as CANCELLED.

The caller still owns the executor lifecycle and may call `executor.shutdown(wait=True)` after `run()` returns.

## Boundary

M30 does not add:

- hard thread termination;
- cooperative cancellation tokens inside user handlers;
- timeout failure semantics;
- process killing;
- async task cancellation.

M31 owns timeout semantics. Stronger cancellation becomes possible only for executors whose capabilities and execution model genuinely support it.
