# PyWorkflowKit V2 — LOT-08 Timeout and Cancellation

Status: implementation baseline  
Target milestone: 2.0.0a2  
Depends on: LOT-00 → LOT-07

## Purpose

LOT-08 makes timeouts and cancellation explicit runtime truth rather than generic failure.

The governing rules are:

```text
timeout
    != confirmed failure

timeout
    != proof external work stopped

cancellation request
    != confirmed cancellation
```

## TimeoutPolicy

The stable V2 declaration remains:

```python
TimeoutPolicy(
    execution_timeout=300.0,
)
```

The value is a local execution deadline policy.

## Execution deadline

WorkflowRuntime converts the relative timeout into an absolute timezone-aware deadline:

```text
runtime clock
    +
execution_timeout
    ↓
TaskExecutionRequest.deadline_at
```

Executors are responsible for enforcement.

WorkflowRuntime does not emulate deadline enforcement when the configured executor cannot
provide it.

## InlineExecutor posture

InlineExecutor executes synchronously in the current process/thread.

It therefore declares:

```text
supports_execution_timeout = false
cancellation_capability = UNSUPPORTED
```

A timed task configured for InlineExecutor fails preflight.

This is deliberate: LOT-08 does not secretly convert InlineExecutor into ThreadExecutor.

## Executor timeout capability

ExecutorDescriptor now includes:

```text
supports_execution_timeout
cancellation_capability
```

An executor that advertises execution timeout support receives deadline_at and must return
structured FailureEvidence when the deadline is exceeded.

## Confirmed timeout

If executor evidence says:

```text
category      = TIMEOUT
uncertainty   = KNOWN
```

then the runtime may record:

```text
TaskAttempt → TIMED_OUT
TaskRun     → TIMED_OUT
WorkflowRun → TIMED_OUT
```

subject to RetryPolicy.

A confirmed timeout may therefore be retryable if structured FailureEvidence explicitly
marks it retryable.

## Timeout retry

Example:

```text
TaskAttempt #1
    → TIMED_OUT
    → RetryDecision.RETRY

TaskAttempt #2
    → SUCCEEDED

TaskRun
    → SUCCEEDED
```

The same TaskRunId is preserved and a new TaskAttemptId is allocated.

## Uncertain timeout

If timeout evidence indicates possible continuing work:

```text
category      = TIMEOUT
uncertainty   = REQUIRES_RECONCILIATION
```

the runtime does not flatten it into TIMED_OUT or FAILED.

Instead:

```text
TaskAttempt → REQUIRES_RECONCILIATION
TaskRun     → UNKNOWN_OUTCOME
WorkflowRun → UNKNOWN_OUTCOME
```

No fresh retry is scheduled before reconciliation.

## CancellationCapability

Executor cancellation strength is explicit:

```text
UNSUPPORTED
BEST_EFFORT
CONFIRMED
```

Capability declaration does not itself claim that a particular cancellation command was
successful.

## CancellationStatus

Each cancellation command returns one of:

```text
REQUESTED
CONFIRMED
UNSUPPORTED
UNCONFIRMED
ALREADY_TERMINAL
```

A bool is intentionally insufficient.

## Executor cancellation boundary

Capability executors implement:

```python
cancel(
    TaskCancellationRequest
) -> TaskCancellationResult
```

TaskCancellationRequest identifies the exact:

```text
WorkflowRunId
TaskRunId
TaskAttemptId
task key
request timestamp
reason
```

## WorkflowRuntime cancellation API

LOT-08 exposes:

```python
runtime.cancel(workflow_run_id)
runtime.cancel_task(task_run_id)
```

Both return immutable CancellationResult.

## Cancellation state flow

Confirmed active cancellation:

```text
TaskAttempt RUNNING
    ↓
CANCELLATION_REQUESTED
    ↓
executor.cancel(...)
    ↓
CONFIRMED
    ↓
TaskAttempt CANCELLED
TaskRun CANCELLED
```

Workflow cancellation additionally stops dispatching tasks that have not started.

## Unsupported cancellation

When the executor cannot cancel active work:

```text
RUNNING
    ↓
CANCELLATION_REQUESTED
    ↓
UNSUPPORTED
    ↓
RUNNING
```

The cancellation command returns UNSUPPORTED.

The runtime does not falsely persist CANCELLED.

## Unconfirmed cancellation

When the executor cannot establish final cancellation truth:

```text
TaskAttempt
    → CANCELLATION_UNCONFIRMED

TaskRun
    → UNKNOWN_OUTCOME

WorkflowRun
    → UNKNOWN_OUTCOME
```

This state is recoverable/reconcilable rather than an ordinary failure.

## Already-terminal semantics

Cancellation of a terminal WorkflowRun or TaskRun is idempotent:

```text
SUCCEEDED / FAILED / CANCELLED / TIMED_OUT
    ↓
cancel(...)
    ↓
ALREADY_TERMINAL
```

No terminal state is rewritten.

## Active execution tracking

WorkflowRuntime keeps only process-local active TaskExecutionRequest references needed to
address cancellation commands.

These references are not durable recovery state.

LOT-09 adds portable ExternalRunRef; LOT-11 adds recovery/reconciliation after process
loss.

## State-machine extensions

LOT-08 permits explicit recovery from rejected cancellation requests:

```text
WorkflowRun:
CANCELLATION_REQUESTED → RUNNING

TaskAttempt:
CANCELLATION_REQUESTED → RUNNING
```

This is used only when cancellation was rejected/unsupported and execution is still known
to be running.

## LOT-08 invariants

```text
deadline declaration
    requires executor capability

timeout KNOWN
    may become TIMED_OUT

timeout uncertain
    becomes reconciliation-required

CANCELLATION_REQUESTED
    != CANCELLED

UNSUPPORTED
    never becomes CANCELLED

UNCONFIRMED
    preserves UNKNOWN_OUTCOME

terminal cancellation
    is idempotent

InlineExecutor
    does not fake interruption
```

## Exit criteria

LOT-08 is complete when:

```text
[ ] TimeoutPolicy is executable
[ ] deadline_at reaches capable executor
[ ] unsupported deadline fails preflight
[ ] confirmed timeout maps to TIMED_OUT
[ ] confirmed timeout integrates with RetryPolicy
[ ] uncertain timeout maps to reconciliation
[ ] TaskCancellationRequest/Result exist
[ ] CancellationStatus is structured
[ ] executor cancellation capability is explicit
[ ] WorkflowRuntime.cancel exists
[ ] WorkflowRuntime.cancel_task exists
[ ] confirmed cancellation is distinct from request
[ ] unsupported cancellation is explicit
[ ] unconfirmed cancellation preserves uncertainty
[ ] already-terminal cancellation is idempotent
[ ] state-machine conformance remains green
[ ] root 1.1 API freeze remains green
[ ] full CI passes
[ ] release qualification passes
```

## Next lot

```text
LOT-09 — ExternalRunRef and UNKNOWN_OUTCOME
```

LOT-09 will make external execution identity durable and portable, so timeout/cancellation
uncertainty can survive process restart and be reconciled against the external provider.
