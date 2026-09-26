# M38 — Reconciliation

M38 is the second milestone of the 0.6.x recovery line.

Its responsibility is narrow:

```text
take ambiguous persisted recovery evidence
        ↓
query external systems through explicit provider adapters
        ↓
normalize external status
        ↓
classify completion
```

It still does not resume the workflow.

## Source scope

The implementation plan defines M38 as:

```text
ExternalRunRef lookup
external status verification
ambiguous completion handling
```

The recovery model requires external systems to be queried before deciding whether
ambiguous work actually completed or must later be retried/resumed.

## Relationship with M37

M37 answers:

```text
Is this persisted run a stale candidate?
Does it contain ambiguous work?
```

M38 answers:

```text
What does the external system currently say about that ambiguous work?
```

M39 will answer:

```text
How should the same WorkflowRun be resumed from the reconciled evidence?
```

## Port

Provider-specific integrations implement:

```python
class ExternalRunVerifier(Protocol):
    @property
    def provider(self) -> str: ...

    def verify(
        self,
        external_ref: ExternalRunRef,
    ) -> ExternalRunStatus: ...
```

The core does not import SDKs for external providers.

## Normalized status

`ExternalRunStatus`:

```text
RUNNING
SUCCEEDED
FAILED
CANCELLED
NOT_FOUND
UNKNOWN
```

Provider adapters own translation from provider-specific states into this normalized
vocabulary.

## Registry

`ExternalRunVerifierRegistry` maps:

```text
ExternalRunRef.provider
        ↓
ExternalRunVerifier
```

Registration is explicit.

Duplicate provider ownership is rejected.

## Task-level disposition

M38 produces one `TaskReconciliation` for each ambiguous non-terminal TaskRun.

`ReconciliationDisposition`:

```text
CONFIRMED_SUCCEEDED
CONFIRMED_FAILED
CONFIRMED_CANCELLED
STILL_RUNNING
MANUAL_REQUIRED
```

These are reconciliation facts, not runtime-state transitions.

## Decision rules

### Confirmed success

All external refs for the task verify as:

```text
SUCCEEDED
```

Result:

```text
CONFIRMED_SUCCEEDED
```

### Confirmed failure

All refs verify as:

```text
FAILED
```

Result:

```text
CONFIRMED_FAILED
```

### Confirmed cancellation

All refs verify as:

```text
CANCELLED
```

Result:

```text
CONFIRMED_CANCELLED
```

### Still running

All refs verify as:

```text
RUNNING
```

Result:

```text
STILL_RUNNING
```

This means recovery must not pretend the workload is complete.

### Manual action

M38 deliberately refuses to infer a completion state when evidence is not conclusive.

Cases include:

```text
no verifier for provider
verifier raised
NOT_FOUND
UNKNOWN
mixed external statuses
RUNNING local work with no ExternalRunRef
```

Result:

```text
MANUAL_REQUIRED
```

## Multiple external references

A TaskRun may carry more than one ExternalRunRef.

M38 only classifies automatically when all normalized statuses agree.

Examples:

```text
SUCCEEDED + SUCCEEDED
    → CONFIRMED_SUCCEEDED

RUNNING + RUNNING
    → STILL_RUNNING

SUCCEEDED + FAILED
    → MANUAL_REQUIRED

FAILED + CANCELLED
    → MANUAL_REQUIRED
```

This prevents hidden assumptions about provider semantics.

## Provider failures

Verifier failures are isolated.

The report contains:

```text
verification_failed:<ExceptionType>
```

It does not copy the provider exception message.

This avoids transporting arbitrary provider error payloads or secrets through recovery
evidence.

## Read-only guarantee

M38 performs no calls to:

```text
save_workflow_run
save_task_run
save_task_attempt
add_event
```

A report can therefore say:

```text
external status = SUCCEEDED
disposition = CONFIRMED_SUCCEEDED
```

while persisted runtime state remains:

```text
WorkflowRun RUNNING
TaskRun RUNNING
TaskAttempt RUNNING
```

That discrepancy is intentional until M39 applies resume semantics.

## Reconciliation report

`ReconciliationReport` exposes:

```text
run_id
task_reconciliations
fully_resolved
has_still_running
requires_manual_action
```

`fully_resolved` means every reconciled task has a confirmed terminal external outcome.

It does not mean the WorkflowRun has been resumed or finalized.

## Durable restart acceptance

Reference acceptance persists ambiguous work to SQLite:

```text
WorkflowRun RUNNING
TaskRun RUNNING
TaskAttempt RUNNING
ExternalRunRef remote-42
```

The store is closed and reopened.

A registered fake provider returns:

```text
SUCCEEDED
```

M38 must then report:

```text
CONFIRMED_SUCCEEDED
```

while all persisted runtime states remain unchanged.

A second acceptance scenario verifies:

```text
external RUNNING
    ↓
STILL_RUNNING
    ↓
not fully resolved
```

## Compatibility

M38 does not change:

- runtime status enums;
- state-machine transitions;
- MetadataStore schema;
- RuntimeEvent taxonomy;
- RunManifest schema;
- Plugin API version;
- executor contracts;
- retry semantics.

No database migration is required.

## Out of scope

M38 does not:

- mark stale attempts FAILED;
- convert confirmed external success into TaskRun success;
- create new attempts;
- resume WorkflowRun execution;
- schedule polling;
- persist reconciliation reports;
- provide provider SDK implementations in core;
- guarantee exactly-once semantics.

These decisions are deferred to M39 or external adapters.

## Next

**M39 — Resume** will consume M37 + M38 evidence and define controlled state transitions
for continuing the same WorkflowRun.
