# PyWorkflowKit V2 — LOT-07 RetryPolicy and Attempt Retry

Status: implementation baseline  
Target milestone: 2.0.0a2  
Depends on: LOT-00 → LOT-06

## Purpose

LOT-07 turns the retry vocabulary prepared in LOT-01 into executable workload-level
semantics.

The central invariant is:

```text
retry
    = same TaskRunId
    + new TaskAttemptId
    + new workload invocation
```

A retry is not a mutation of an existing attempt.

## V1 and V2 policy separation

The 1.1 root remains frozen:

```python
from pyworkflowkit import RetryPolicy
```

This is the legacy 1.1 policy.

Canonical V2 authoring uses:

```python
from pyworkflowkit.policies import RetryPolicy
```

The two contracts intentionally coexist during migration.

## V2 RetryPolicy

The V2 policy models:

```text
max_attempts
backoff_strategy
initial_delay_seconds
max_delay_seconds
jitter
retryable_failure_categories
total_budget_seconds
reconciliation_required
```

max_attempts includes the initial attempt.

Therefore:

```text
max_attempts = 1
    → no retry

max_attempts = 3
    → at most TaskAttempt #1, #2 and #3
```

## Structured retry evidence

Retry decisions consume FailureEvidence:

```text
FailureEvidence
├── category
├── retryability
├── uncertainty
├── error_code
├── execution identities
└── external execution reference?
```

The runtime does not decide retry from exception-message regexes.

The stable retryability values remain:

```text
RETRYABLE
NON_RETRYABLE
UNKNOWN
RETRYABLE_AFTER_RECONCILIATION
```

## RetryDecision

The LOT-01 disposition vocabulary is preserved:

```text
RETRY
DO_NOT_RETRY
RECONCILE
ABORT
CANCEL
ESCALATE
```

LOT-07 adds RetryEvaluation, which records:

```text
decision
reason
delay_seconds
attempt_number
max_attempts
failure_category
retryability
uncertainty
budget_remaining_seconds?
```

## Decision precedence

The evaluator is fail-closed.

The decision order is:

```text
uncertain outcome?
    ├── yes + reconciliation_required
    │       → RECONCILE
    │
    └── yes + reconciliation disabled
            → ESCALATE

known outcome
    ↓
max attempts exhausted?
    → DO_NOT_RETRY

failure explicitly non-retryable?
    → DO_NOT_RETRY

retryability unknown?
    → DO_NOT_RETRY

category allowlist configured and category absent?
    → DO_NOT_RETRY

retry budget exceeded?
    → DO_NOT_RETRY

otherwise
    → RETRY
```

## UNKNOWN_OUTCOME rule

The runtime never performs:

```text
UNKNOWN_OUTCOME
    → fresh TaskAttempt
```

Instead:

```text
UNKNOWN_OUTCOME
    ↓
RECONCILE
or
ESCALATE
```

When RECONCILE is selected:

```text
TaskAttempt
    → REQUIRES_RECONCILIATION

TaskRun
    → UNKNOWN_OUTCOME

WorkflowRun
    → UNKNOWN_OUTCOME
```

Pending downstream tasks remain pending. No fail-fast skip is manufactured because the
workflow has not established a definitive failure.

LOT-09 and LOT-11 will add the external reference and reconciliation mechanisms that
continue this state.

## Backoff

Stable backoff strategies are:

```text
NONE
FIXED
LINEAR
EXPONENTIAL
```

For a failed attempt N and initial delay D:

```text
NONE         0
FIXED        D
LINEAR       D × N
EXPONENTIAL  D × 2^(N-1)
```

max_delay_seconds caps the computed value before jitter.

## Jitter

LOT-07 provides:

```text
RetryJitter.NONE
RetryJitter.FULL
```

FULL jitter selects a value in:

```text
0 <= delay <= computed_backoff
```

The entropy source is injectable through RetryEvaluator, making tests deterministic.

Out-of-range or non-finite injected jitter is rejected.

## Retry budget

total_budget_seconds is a task-run-level elapsed-time budget.

Before scheduling a retry:

```text
elapsed task time
    + computed retry delay
    <= total retry budget
```

must hold.

If not:

```text
RetryDecision.DO_NOT_RETRY
reason = retry_budget_exhausted
```

The initial workload attempt is still permitted; the budget controls subsequent retries.

## Waiting boundary

WorkflowRuntime accepts an injectable RetryWaiter.

Production default:

```text
SystemRetryWaiter
    → time.sleep(delay)
```

Tests can inject a recording/no-op waiter.

This avoids sleeping in deterministic retry conformance tests.

## Runtime lifecycle

For a retryable first failure:

```text
TaskRun TR-1
    → RUNNING

TaskAttempt TA-1
    → STARTING
    → RUNNING
    → FAILED

RetryEvaluator
    → RETRY
    → delay

TaskAttempt TA-2
    → STARTING
    → RUNNING
    → SUCCEEDED

TaskRun TR-1
    → SUCCEEDED
```

The TaskRun does not transition to FAILED between attempts.

It becomes FAILED only after the final DO_NOT_RETRY decision.

## Retry exhaustion

Example:

```text
RetryPolicy(max_attempts=3)

TA-1 FAILED → RETRY
TA-2 FAILED → RETRY
TA-3 FAILED → DO_NOT_RETRY

TaskRun → FAILED
WorkflowRun → FAILED
```

All attempts remain queryable through MetadataStore.

## Category filtering

retryable_failure_categories is typed as FailureCategory values.

When empty:

```text
FailureEvidence.retryability
    is the primary retry signal
```

When configured:

```text
failure must be RETRYABLE
and
failure.category must be in the allowlist
```

This prevents stringly-typed exception matching.

## Retry amplification

ExecutorDescriptor now declares:

```text
performs_implicit_workload_retry: bool
```

The stable InlineExecutor declares false.

If an executor declares implicit workload retry while TaskDefinition also requests
max_attempts > 1, WorkflowRuntime fails during preflight.

Therefore equivalent retry scopes cannot be silently stacked.

Provider-internal retries of a distinct lower scope remain a later integration concern.

## Diagnostics

Every failed attempt produces a structured retry evaluation diagnostic:

```text
PWK-RETRY-DECISION
├── decision
├── reason
├── attempt_number
├── max_attempts
├── delay_seconds
├── failure_category
├── retryability
├── uncertainty
└── budget_remaining_seconds?
```

When RETRY is selected, an additional diagnostic is emitted:

```text
PWK-RETRY-SCHEDULED
├── current attempt
├── next attempt
├── delay
└── reason
```

The diagnostic contract makes retry behavior observable without parsing log messages.

## Runtime result on uncertainty

WorkflowResult now accepts:

```text
terminal WorkflowRun status
or
UNKNOWN_OUTCOME
```

This is necessary because UNKNOWN_OUTCOME is a caller-visible runtime outcome even though
the persisted workflow remains recoverable and non-terminal.

Other non-terminal states such as RUNNING or CANCELLATION_REQUESTED remain invalid for a
WorkflowResult returned by the synchronous run path.

## Executor exception boundary

The runtime still translates an exception escaping Executor.execute into structured
FailureEvidence.

The default classification is conservative:

```text
category      = INTERNAL
retryability  = NON_RETRYABLE
uncertainty   = KNOWN
```

Therefore an arbitrary Python exception is not retried merely because max_attempts > 1.

Executors/adapters that know a failure is transient must express that fact through
structured FailureEvidence.

## LOT-07 invariants

```text
retry
    → same TaskRunId

retry
    → new TaskAttemptId

TaskRun
    stays RUNNING between attempts

attempt failure
    is persisted before next attempt

max_attempts
    includes initial attempt

NON_RETRYABLE
    never retries

Retryability.UNKNOWN
    fails closed

UNKNOWN_OUTCOME
    never blind retries

retry budget
    includes scheduled delay

equivalent executor retry
    cannot stack implicitly

root 1.1 RetryPolicy
    remains unchanged
```

## Exit criteria

LOT-07 is complete when:

```text
[ ] canonical V2 RetryPolicy exists
[ ] RetryDecision vocabulary remains stable
[ ] RetryEvaluation exposes decision evidence
[ ] fixed backoff works
[ ] linear backoff works
[ ] exponential backoff works
[ ] maximum delay is enforced
[ ] full jitter is bounded and injectable
[ ] category filtering is typed
[ ] total retry budget is enforced
[ ] uncertainty produces RECONCILE/ESCALATE
[ ] retry creates new TaskAttemptId
[ ] retry preserves TaskRunId
[ ] attempt history remains persisted
[ ] TaskRun fails only after final retry decision
[ ] retry diagnostics are emitted
[ ] RetryWaiter is injectable
[ ] implicit equivalent executor retry is rejected
[ ] timeout execution remains deferred to LOT-08
[ ] root 1.1 API freeze remains green
[ ] full CI passes
[ ] release qualification passes
```

## Next lot

```text
LOT-08 — Timeout and Cancellation
```

LOT-08 will add execution deadlines and cancellation truth without treating local timeout
as proof that external work stopped.
