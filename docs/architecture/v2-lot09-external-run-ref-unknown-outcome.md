# PyWorkflowKit V2 — LOT-09 ExternalRunRef and UNKNOWN_OUTCOME

## Status

Implemented on top of LOT-08.

LOT-09 closes the gap between an uncertain local runtime outcome and the durable
identity of work owned by an external runtime.

## Core rule

```text
UNKNOWN_OUTCOME
    != FAILED
    != safe to retry blindly
```

When PyWorkflowKit cannot prove the final outcome of external work, the current
TaskAttempt remains the reconciliation target. A new TaskAttempt is not created until
later reconciliation establishes that doing so is safe.

## ExternalRunRef

The canonical V2 value remains:

```text
provider
kind
external_run_id
status_hint?
status_locator?
correlation_id?
causation_id?
metadata
```

`ExternalRunRef` is evidence and correlation data. It does not import or duplicate the
foreign runtime state machine.

## Attempt ownership

External execution identity is scoped to the concrete TaskAttempt that created it:

```text
WorkflowRun
  └── TaskRun
        ├── TaskAttempt #1
        │     └── ExternalRunRef JOB-1
        └── TaskAttempt #2
              └── ExternalRunRef JOB-2
```

This matters for retry safety. Reusing only TaskRun ownership would make two foreign
executions created by two attempts indistinguishable.

## Executor result boundary

`TaskExecutionResult` may now return normal external execution evidence:

```python
TaskExecutionResult(
    output=...,
    external_runs=(external_ref,),
)
```

A failure may also carry its primary foreign identity through
`FailureEvidence.external_run`.

Cancellation adapters may return the foreign identity through
`TaskCancellationResult.external_runs`, including when the cancellation result is
`UNCONFIRMED`.

WorkflowRuntime persists all three sources into the MetadataStore and de-duplicates the
same semantic reference within one attempt.

## UNKNOWN_OUTCOME path

For uncertain external failure:

```text
Executor
  ↓
FailureEvidence
  uncertainty = REQUIRES_RECONCILIATION
  retryability = RETRYABLE_AFTER_RECONCILIATION
  external_run = ExternalRunRef(...)
  ↓
WorkflowRuntime
  ├── persists ExternalRunRef on current TaskAttempt
  ├── TaskAttempt → REQUIRES_RECONCILIATION
  ├── TaskRun     → UNKNOWN_OUTCOME
  ├── WorkflowRun → UNKNOWN_OUTCOME
  └── DOES NOT create Attempt N+1
```

This preserves the LOT-07 rule that uncertain work cannot trigger a blind retry.

## Qualified scenarios

LOT-09 qualifies:

1. successful external execution persists its ExternalRunRef;
2. uncertain external execution keeps the foreign identity;
3. UNKNOWN_OUTCOME creates no blind retry;
4. retry creates a new TaskAttempt and keeps each external run reference on the attempt
   that created it;
5. unconfirmed cancellation preserves the foreign execution identity for later
   reconciliation;
6. duplicate exposure of the same reference through TaskExecutionResult and
   FailureEvidence does not duplicate persisted evidence.

## Compatibility

The frozen 1.1 package root remains unchanged.

LOT-09 changes only qualified V2 surfaces:

```text
pyworkflowkit.executors
pyworkflowkit.runtime
pyworkflowkit.persistence
```

## Next lot

```text
LOT-10 — SQLite Durable MetadataStore
```

LOT-10 will make the V2 WorkflowRun / TaskRun / TaskAttempt / ExternalRunRef evidence
survive process restart. LOT-11 can then use that durable evidence for recovery and
reconciliation.
