# PyWorkflowKit V0.1 Release Readiness

## Status

**QUALIFIED — 0.1.0a1 candidate**

Qualification date: **2026-09-25**

Qualified implementation commit:

```text
5af0010bfbebf4caa059c895573c45ee79f4c137
```

GitHub Actions qualification run:

```text
36179980996
```

## Release target

```text
Package version: 0.1.0a1
Manifest schema: 1
Python: >=3.11
Runtime model: embedded / sequential / in-process
Metadata backend: MemoryMetadataStore
Executor: LocalExecutor
Failure policy: FAIL_FAST
```

## Required gates

| Gate | Result |
|---|---|
| Ruff lint | PASS |
| Ruff format | PASS |
| mypy strict | PASS |
| Build wheel + sdist | PASS |
| Wheel install smoke | PASS |
| Python 3.11 tests + branch coverage | PASS |
| Python 3.12 tests + branch coverage | PASS |
| Python 3.13 tests + branch coverage | PASS |
| V0.1 reference acceptance suite | PASS |
| Executable hello-world example | PASS |
| Emitted manifest JSON parse smoke | PASS |

## Reference workflow acceptance baseline

The release gate in `tests/reference/test_v0_1_acceptance.py` freezes the observable semantics of the V0.1 runtime.

### RF-001 — Single task success

```text
A
```

Expected:

```text
WorkflowRun SUCCEEDED
TaskRun A SUCCEEDED
Attempt 1 SUCCEEDED
WORKFLOW_STARTED
TASK_READY
TASK_STARTED
TASK_SUCCEEDED
WORKFLOW_SUCCEEDED
```

Result: **PASS**

### RF-002 — Linear dependency execution

```text
A → B → C
```

Expected:

- deterministic order A, B, C;
- upstream output propagation through `RunContext`;
- terminal workflow success.

Result: **PASS**

### RF-003 — Diamond workflow

```text
    A
   / \
  B   C
   \ /
    D
```

Expected V0.1 semantics:

- graph expresses B/C structural parallelism;
- sequential runtime dispatch remains deterministic;
- execution order is A, B, C, D.

Result: **PASS**

### RF-004 — Retry then success

Expected:

- one `TaskRun`;
- Attempt 1 FAILED;
- Attempt 2 SUCCEEDED;
- `TASK_RETRYING` emitted;
- no intermediate terminal `TASK_FAILED`.

Result: **PASS**

### RF-005 — Retry exhaustion and FAIL_FAST

Expected:

- failed task becomes FAILED after retry exhaustion;
- descendants become SKIPPED / DEPENDENCY_FAILED;
- independent undispatched tasks become SKIPPED / FAIL_FAST_ABORT;
- workflow becomes FAILED.

Result: **PASS**

### RF-006 — Portable deterministic execution evidence

Expected:

- `RunManifest` reconstructs from persisted facts;
- repeated reconstruction is deterministic;
- sensitive workflow parameters are redacted;
- artifacts and external references are preserved.

Result: **PASS**

### RF-007 — Invalid cycle rejected before execution

Expected:

- cycle validation fails before runtime metadata is created;
- no TaskRun or RuntimeEvent is persisted.

Result: **PASS**

## Core architecture gates

The qualified V0.1 runtime preserves these boundaries:

```text
Definition describes
Graph validates structure
Planner computes deterministic static order
ReadyTaskResolver decides runtime eligibility
StateMachine owns legal state transitions
Executor executes trusted workload code
RetryEngine decides retry
FailurePropagator classifies fail-fast skips
MetadataStore persists runtime facts
RuntimeEvent records ordered evidence
RunManifestBuilder reconstructs final portable evidence
```

## V0.1 included scope

- workflow/task definitions;
- DAG validation;
- deterministic planning;
- sequential embedded Runner;
- LocalExecutor;
- MemoryMetadataStore + UnitOfWork;
- runtime state transitions;
- retry/backoff;
- retryable error categories;
- fail-fast propagation;
- runtime events;
- artifacts;
- external run references;
- deterministic final manifest;
- sensitive parameter redaction;
- Python 3.11–3.13 qualification.

## Explicitly deferred beyond V0.1

- durable SQLite persistence;
- PostgreSQL persistence;
- schema migrations;
- CLI;
- decorators;
- configuration layer;
- plugin discovery;
- PyIngestKit adapter;
- concurrent dispatch;
- thread/process/async/subprocess executors;
- hard timeout;
- hard cancellation;
- crash recovery;
- resume;
- reconciliation.

## Release conclusion

The V0.1 implementation satisfies the acceptance baseline required for promotion to:

```text
0.1.0a1
```

This qualification does **not** declare the public API stable.

The alpha establishes the first executable contract:

```text
DEFINE
  ↓
VALIDATE
  ↓
PLAN
  ↓
EXECUTE
  ↓
RETRY / FAIL FAST
  ↓
PERSIST
  ↓
RECORD EVENTS
  ↓
PRODUCE FINAL EVIDENCE
```

> **Reliable workflows without running a workflow platform.**
