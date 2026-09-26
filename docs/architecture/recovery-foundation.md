# M37 — Recovery Foundation

M37 opens the 0.6.x recovery line with read-only recovery diagnostics over persisted
runtime evidence.

It does **not** perform reconciliation or resume.

## Source boundary

The recovery model already defines the essential problem:

```text
WorkflowRun RUNNING
TaskRun RUNNING
TaskAttempt RUNNING

but the original PyWorkflowKit process no longer exists
```

It also requires recovery to reason from:

```text
persistent evidence
idempotency
external reconciliation when needed
```

and explicitly forbids silent recovery.

M37 therefore introduces classification before mutation.

## Recovery pipeline after M37

```text
MetadataStore
    ↓
WorkflowRun
TaskRuns
TaskAttempts
RuntimeEvents
ExternalRunRefs
    ↓
RecoveryInspector
    ↓
RecoveryAssessment
    ├── liveness
    ├── resume eligibility
    ├── reconciliation requirement
    └── idempotency metadata
```

No state transition occurs in this pipeline.

## MetadataStore extension

M37 adds:

```python
list_workflow_runs() -> Sequence[WorkflowRun]
```

to the MetadataStore read model.

This enables candidate discovery without introducing a scheduler or recovery daemon.

Implemented built-in backends:

```text
MemoryMetadataStore
SqlAlchemyMetadataStore
SQLiteMetadataStore via SQLAlchemy
PostgresMetadataStore via SQLAlchemy
```

No persistence-schema migration is required.

## Liveness classification

`RecoveryLiveness` contains:

```text
TERMINAL
ACTIVE
STALE_CANDIDATE
UNKNOWN
```

### TERMINAL

The WorkflowRun is already:

```text
SUCCEEDED
FAILED
CANCELLED
```

No resume is eligible.

### ACTIVE

The run is non-terminal and the latest persisted evidence is newer than the configured
stale threshold.

### STALE_CANDIDATE

The run is non-terminal and the latest persisted evidence is at least
`stale_after` old.

The word **candidate** is mandatory.

A timestamp threshold cannot prove that a workload stopped.

### UNKNOWN

The inspector cannot make a safe time-based classification.

Current cases:

```text
no timestamp evidence
latest evidence is in the future relative to the injected Clock
```

Unknown is never silently promoted to stale.

## Evidence timestamp

M37 computes the latest durable timestamp across:

```text
WorkflowRun created/started/finished
TaskRun created/started/finished
TaskAttempt started/finished
RuntimeEvent occurred_at
```

This intentionally reuses existing durable state.

M37 does not add:

```text
heartbeat_at
worker_id
lease_expires_at
```

Those fields remain unnecessary until ownership/lease semantics are explicitly designed.

## Resume eligibility

`ResumeEligibility` contains:

```text
NOT_ELIGIBLE
ELIGIBLE
REQUIRES_RECONCILIATION
```

This is an assessment for M39. It is not a resume API.

### NOT_ELIGIBLE

Examples:

```text
terminal workflow
active workflow
unknown liveness
```

### ELIGIBLE

A stale candidate is structurally eligible when persisted evidence contains no ambiguous
running or external work.

That does **not** prove side-effect safety.

### REQUIRES_RECONCILIATION

A stale candidate requires M38 when it contains any of:

```text
TaskRun RUNNING
TaskAttempt RUNNING
ExternalRunRef owned by a non-terminal TaskRun
```

Those facts mean PyWorkflowKit cannot safely decide whether the workload completed,
failed, or remains active.

## External evidence

M37 distinguishes:

```text
all ExternalRunRefs
vs
ExternalRunRefs attached to non-terminal tasks
```

An ExternalRunRef from an already-terminal task remains historical evidence and does not
by itself block resume eligibility.

External work attached to a non-terminal task is ambiguous and requires reconciliation.

## Idempotency metadata

The recovery model identifies `task_run_id` as a suitable technical deduplication key
across attempts.

M37 exposes:

```text
TaskIdempotencyMetadata
    task_id
    task_run_id
    idempotency_key = task_run_id
    attempt_count
```

Example:

```text
TaskRun T-123
    ├── Attempt 1
    ├── Attempt 2
    └── Attempt 3

idempotency_key = T-123
```

This does not make the user workload idempotent.

It gives the workload a stable identity that can be used by external systems.

## WorkflowRuntime facade

The public facade adds diagnostic helpers:

```python
runtime.recovery_assessment(
    run_id,
    stale_after_seconds=300,
)

runtime.stale_run_candidates(
    stale_after_seconds=300,
)
```

Both are read-only.

## Clock

RecoveryInspector uses the existing Clock port.

This keeps stale detection deterministic in tests and avoids direct wall-clock calls in
application logic.

## Concurrency and consistency

M37 is diagnostic.

Its read operations do not acquire a cross-entity snapshot lock while loading run,
tasks, attempts, events, and external references.

Therefore an actively changing run can produce a transient assessment.

That is acceptable for candidate inspection.

M38 must define stronger reconciliation/locking semantics before applying recovery state
changes.

## Durable restart acceptance

M37 reference acceptance persists:

```text
WorkflowRun RUNNING
TaskRun RUNNING
TaskAttempt RUNNING
RuntimeEvent TASK_STARTED
ExternalRunRef
```

to SQLite, closes the store, reopens it, then proves that:

```text
liveness = STALE_CANDIDATE
resume = REQUIRES_RECONCILIATION
idempotency key survives
persisted state remains RUNNING
```

This is the first end-to-end crash-evidence recovery diagnostic.

## No heartbeat or lease yet

Earlier architecture correctly warned against adding:

```text
heartbeat_at
worker_id
lease_expires_at
```

before explicit recovery/ownership semantics exist.

M37 still follows that constraint.

A future recovery line may add such evidence only with clear ownership and expiry
contracts.

## Security

RecoveryAssessment deliberately does not copy:

```text
workflow parameters
TaskResult outputs
error message bodies
external metadata
artifact metadata
```

Its purpose is runtime classification, not payload transport.

## M37 acceptance gates

- MetadataStore lists workflow runs deterministically;
- Memory and relational implementations satisfy the expanded port;
- terminal runs are not recovery candidates;
- recent evidence classifies ACTIVE;
- old evidence classifies STALE_CANDIDATE;
- absent/future timestamps classify UNKNOWN;
- running TaskRun requires reconciliation;
- running TaskAttempt requires reconciliation;
- unresolved external work requires reconciliation;
- external refs from terminal tasks do not block eligibility;
- task_run_id is stable idempotency key across attempts;
- stale candidate discovery excludes active and terminal runs;
- SQLite restart preserves stale crash evidence;
- M37 never mutates recovery state;
- Python 3.11 / 3.12 / 3.13;
- Ruff;
- strict mypy;
- branch coverage >= 90%;
- reference acceptance;
- wheel/version smoke;
- PostgreSQL regression contract;
- security gates.

## Out of scope

M37 does not implement:

- attempt failure during recovery;
- remote status queries;
- reconciliation decisions — M38;
- resume execution — M39;
- non-blocking retry scheduling — M40;
- heartbeats;
- leases;
- worker ownership;
- exactly-once execution;
- automatic replay;
- recovery daemon/scheduler;
- distributed recovery.

## Next

**M38 — Reconciliation** will define how ambiguous persisted work is classified using
executor/external evidence before any resume decision.
