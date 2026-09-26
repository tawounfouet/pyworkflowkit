# ThreadExecutor

M28 introduces the first genuinely parallel executor in PyWorkflowKit.

`ThreadExecutor` uses Python's `ThreadPoolExecutor` and implements the existing
synchronous `Executor.execute()` contract while also exposing submission and
completion-transfer primitives for the future concurrent Runner.

## Capabilities

A ThreadExecutor with `max_workers=N` declares:

```text
supports_parallelism = true
timeout              = soft
cancellation         = none
max_concurrency       = N
```

Cancellation remains `none` until M30 defines runtime cancellation semantics.

## Submission

```text
TaskAttempt
    ↓
ThreadExecutor.submit()
    ↓
ExecutionHandle
    ↓
ThreadPoolExecutor
    ↓
worker invokes trusted Python handler
    ↓
AttemptCompletion
    ↓
CompletionQueue
```

The worker does not transition WorkflowRun, TaskRun, or TaskAttempt state.

## Soft timeout semantics

`ThreadExecutor.wait(handle, timeout=...)` returns a boolean:

- `True`: the underlying future is terminal;
- `False`: the wait expired.

A false result does not stop or cancel the workload. The worker continues and later
publishes exactly one `AttemptCompletion`.

This is intentionally not the final runtime timeout policy. M31 owns
`ExecutionTimeoutError`, capability validation, and retry integration.

## Shutdown

`shutdown(wait=True)`:

- stops new submissions;
- waits for submitted work by default;
- does not cancel queued/running futures in M28;
- preserves completion publication for work that finishes.

Submitting after shutdown raises `ExecutorShutdownError`.

## Duplicate attempt protection

One `TaskAttemptId` may be submitted at most once to a ThreadExecutor instance.
Duplicate submission raises `DuplicateExecutionSubmissionError`.

## Shared invocation mechanics

`LocalExecutor` and `ThreadExecutor` share only the trusted-Python invocation and
result-normalization helper. Their scheduling/execution strategies remain separate.

## Boundary

M28 does not introduce:

- concurrent DAG coordination;
- READY-task dispatch policy;
- coordinator-owned state transitions;
- cancellation semantics;
- terminal timeout failure;
- retry decisions inside the executor.

M29 consumes the M25–M28 primitives to build the concurrent coordinator.
