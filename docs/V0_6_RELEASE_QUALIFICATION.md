# PyWorkflowKit 0.6.0 — Transverse Release Qualification

Date: 2026-09-27

## Objective

Promote the completed 0.6 development line from `0.6.0a4` to stable `0.6.0`
without adding new functional scope.

The qualification consolidates:

```text
M37 Recovery Foundation
M38 Reconciliation
M39 Resume
M40 Non-blocking Retry
```

## Release principle

The release is acceptable only if recovery behaves as one coherent durable contract across
the runtime rather than as four independent features.

No qualification change may silently alter:

```text
WorkflowRun / TaskRun / TaskAttempt lifecycle enums
RetryPolicy / RetryEngine authority
RuntimeEvent taxonomy
RunManifest schema
Plugin API version
package-root public surface
executor capability contracts
resume identity semantics
PyIngestKit atomic-workload boundary
scheduler / control-plane boundary
```

## Recovery contract freeze

### Recovery is evidence-driven

M37 remains diagnostic. A stale threshold identifies a candidate and does not prove that
a workload stopped.

Canonical liveness values remain:

```text
terminal
active
stale_candidate
unknown
```

Canonical resume eligibility remains:

```text
not_eligible
eligible
requires_reconciliation
```

### Reconciliation remains conservative

External verification normalizes provider state to:

```text
running
succeeded
failed
cancelled
not_found
unknown
```

The reconciliation dispositions remain:

```text
confirmed_succeeded
confirmed_failed
confirmed_cancelled
still_running
manual_required
```

Unknown, missing, conflicting, or unverifiable evidence must never be converted into
silent success.

### Resume preserves execution identity

```text
resume  -> same WorkflowRun
rerun   -> new WorkflowRun
replay  -> new WorkflowRun + historical references
```

A resumed run must not re-execute already-SUCCEEDED TaskRuns by default.

Portable dependency outputs may be checkpointed durably. Missing required recovery
evidence must fail explicitly rather than being reconstructed by guesswork or opaque
pickle state.

### Retry wait is evidence, not a new lifecycle state

0.6.0 does not add `RETRY_WAITING` or `RETRYING` to `TaskRunStatus`.

The durable representation remains:

```text
TaskRun RUNNING
Attempt N FAILED
retry_eligible_at = wall-clock timestamp
```

The concurrent coordinator uses a local monotonic deadline for process-local waiting,
while `retry_eligible_at` is the portable wall-clock proof that survives restart.

The sequential Runner may still block locally, but it must persist retry eligibility
before sleeping.

## Persistence qualification

The stable migration chain is:

```text
0001_runtime_metadata
        ↓
0002_task_output_checkpoints
        ↓
0003_retry_eligible_at
```

Both SQLite and PostgreSQL must reach `0003_retry_eligible_at` from a fresh schema and
must remain idempotent when the upgrade command is repeated.

The installed wheel must contain all three migration revisions.

## Transverse contract checks

`tests/reference/test_v0_6_release_qualification.py` freezes:

- lifecycle enum sets;
- absence of a retry-wait TaskRun state;
- presence of durable `TaskAttempt.retry_eligible_at`;
- recovery liveness values;
- resume eligibility values;
- external reconciliation status values;
- reconciliation disposition values;
- RunManifest schema version `1`;
- Plugin API version `1`;
- intentionally small package-root public API;
- packaged migration revisions through `0003_retry_eligible_at`.

## Functional qualification

The complete reference suite must continue to prove:

- M37 stale candidate and ambiguity classification;
- M38 external reconciliation after durable restart;
- M39 same-run resume after SQLite close/reopen;
- restored durable dependency outputs;
- preserved completed TaskRuns;
- monotonic continuation of the existing event sequence;
- M40 retry wait surviving restart;
- creation of Attempt N+1 only after safe recovery;
- non-blocking retry backoff in ConcurrentRunner;
- unrelated READY work progressing during retry wait;
- existing 0.1-0.5 sequential, persistence, CLI, plugin, concurrency, timeout,
  cancellation, executor, observability, and security acceptance scenarios.

## Build qualification

The release build must prove all three version surfaces are exactly `0.6.0`:

```text
importlib.metadata.version("pyworkflowkit")
pyworkflowkit.__version__
pyworkflow version
```

Supported Python:

```text
3.11
3.12
3.13
```

All supported versions run the complete pytest suite with branch coverage >= 90%.

## Security qualification

The existing blocking release gates remain:

```text
Bandit
pip-audit
detect-secrets
```

Dependency Review remains integrated for pull requests when the repository platform
capability is available.

## Release decision

Promotion to `0.6.0` is permitted only when every blocking CI job on the release HEAD
is green.

The release branch adds no M41 scope. Any defect discovered during qualification must be
fixed narrowly and requalified on the same final HEAD.

## Post-release roadmap

```text
0.6.0
  Durable recovery / reconciliation / same-run resume
        ↓
0.7-0.9
  Compatibility / Ecosystem / Stabilization
        ↓
1.0.0
  Stable embedded runtime core contract
```
