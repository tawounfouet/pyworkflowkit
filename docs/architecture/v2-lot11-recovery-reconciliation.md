# PyWorkflowKit V2 — LOT-11 Recovery and Reconciliation

## Status

Implemented on top of LOT-10 durable SQLite persistence.

LOT-11 turns persisted uncertainty into an explicit recovery workflow. It does not invent
provider truth, does not retry ambiguous work, and does not automatically resume a
workflow after reconciliation.

## Recovery inspection

The qualified V2 diagnostics surface now exposes:

```text
RecoveryInspector
RecoveryAssessment
TaskRecoveryAssessment
RecoveryDisposition
```

The dispositions are:

```text
NO_ACTION
READY
REQUIRES_RECONCILIATION
MANUAL_REQUIRED
```

The inspector reads only MetadataStore evidence. It never mutates runtime state.

A non-terminal attempt with an attempt-scoped ExternalRunRef is classified as requiring
reconciliation. A non-terminal attempt without external evidence is classified as manual
recovery because PyWorkflowKit cannot safely infer what happened after process loss.

A terminal TaskAttempt paired with a non-terminal TaskRun is also recoverable evidence:
the durable attempt state is sufficient to repair the lagging task state without querying
an external provider.

## Provider reconciliation contract

The qualified V2 runtime surface now exposes:

```text
ExternalRunStatus
ExternalRunVerifier
ExternalRunVerifierRegistry
ExternalRunObservation
ReconciliationDisposition
TaskReconciliation
ReconciliationReport
ReconciliationService
```

Provider status is normalized to:

```text
RUNNING
SUCCEEDED
FAILED
CANCELLED
NOT_FOUND
UNKNOWN
```

Provider adapters own the query. PyWorkflowKit owns only the normalized reconciliation
decision.

## Same-attempt invariant

The critical LOT-09 invariant remains:

```text
UNKNOWN_OUTCOME
      │
      ▼
reconcile existing ExternalRunRef
      │
      ├── SUCCEEDED → same TaskAttempt → SUCCEEDED
      ├── FAILED    → same TaskAttempt → FAILED
      ├── CANCELLED → same TaskAttempt → CANCELLED
      ├── RUNNING   → no mutation
      └── unknown   → MANUAL_REQUIRED
```

Reconciliation never creates Attempt N+1.

A new attempt may only be created by a later resume/retry decision after ambiguity has
been resolved.

## Secret-safe verification failures

Verifier exceptions are isolated.

PyWorkflowKit records only:

```text
verification_failed:<ExceptionType>
```

The provider exception message is not copied into reconciliation evidence.

## Durable state repair

LOT-11 handles two distinct recovery sources.

### External provider truth

When the latest attempt is non-terminal and has ExternalRunRef evidence, the registered
provider verifier is queried.

A unanimous conclusive status is applied through the V2 state machines and MetadataStore
compare-and-set writes.

### Local durable truth

If a crash occurred after a terminal TaskAttempt was persisted but before its TaskRun was
updated, the terminal attempt is treated as durable authority and the TaskRun is repaired.

This includes:

```text
SUCCEEDED
FAILED
CANCELLED
TIMED_OUT
```

The UNKNOWN_OUTCOME state machines therefore allow reconciliation to TIMED_OUT when
durable timeout evidence already exists.

## Workflow state after reconciliation

Once every ambiguous task is resolved:

```text
any FAILED task       → WorkflowRun.FAILED
any TIMED_OUT task    → WorkflowRun.TIMED_OUT
any CANCELLED task    → WorkflowRun.CANCELLED
all tasks terminal
  and successful      → WorkflowRun.SUCCEEDED
downstream work left  → WorkflowRun.RUNNING
```

If provider work is still running or evidence is inconclusive, the workflow remains
unresolved.

## WorkflowRuntime facade

The canonical V2 WorkflowRuntime now exposes:

```python
runtime.recovery_assessment(run_id)
runtime.recovery_candidates()
runtime.register_external_run_verifier(verifier)
runtime.reconcile_run(run_id)
```

These APIs operate on the injected canonical V2 MetadataStore.

## Restart acceptance

LOT-11 proves the following sequence against SQLite:

```text
process A
   │
   ├── WorkflowRun = UNKNOWN_OUTCOME
   ├── TaskRun = UNKNOWN_OUTCOME
   ├── TaskAttempt = REQUIRES_RECONCILIATION
   ├── ExternalRunRef = REMOTE-42
   └── process/store closes
             │
             ▼
          SQLite
             │
             ▼
process B
   │
   ├── discovers the same WorkflowRun
   ├── loads the same TaskAttempt
   ├── queries REMOTE-42
   ├── receives SUCCEEDED
   └── updates the same attempt/task/run
```

The acceptance test additionally proves:

```text
attempt count before = 1
attempt count after  = 1
```

No duplicate external execution is manufactured.

## Explicit non-goals

LOT-11 does not add:

- automatic global recovery polling;
- heartbeats or distributed leases;
- automatic provider discovery;
- automatic workflow resume;
- durable arbitrary task outputs;
- event/manifest/lineage expansion.

These remain separate contracts.

## Next lot

The next implementation area is LOT-12, which owns the richer V2 event, manifest,
lineage, inspection, and durable-output evidence model.
