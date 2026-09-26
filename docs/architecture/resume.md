# M39 — Resume

M39 is the third milestone of the 0.6.x recovery line.

Its responsibility is:

```text
continue one existing WorkflowRun
from durable recovery evidence
without re-executing completed tasks
```

## Source semantics

The roadmap defines:

```text
resume
    same WorkflowRun

rerun
    new WorkflowRun
```

The reference acceptance scenario requires:

```text
A SUCCEEDED
B SUCCEEDED
C PENDING
```

followed by resume of the same run, without re-executing completed tasks.

M39 implements that contract.

## Recovery pipeline

```text
M37
stale candidate detection
        ↓
M38
external reconciliation
        ↓
M39
apply safe reconciliation
        ↓
restore durable dependency outputs
        ↓
execute only remaining work
        ↓
same WorkflowRun reaches terminal state
```

## Same-run identity

Resume preserves:

```text
WorkflowRun.run_id
existing TaskRun IDs
existing TaskAttempt history
existing RuntimeEvent history
```

A remaining task receives a new TaskAttempt only when it actually executes.

M39 never calls the runtime ID factory for a new WorkflowRun.

## Completed-task preservation

Persisted TaskRuns already in:

```text
SUCCEEDED
```

are not dispatched again.

Their handlers do not even need to be registered in the resumed process.

This is stronger than merely skipping handler invocation after preflight: M39 preflights
handlers only for tasks that still need execution.

## Durable output checkpoint problem

Normal execution passes small task outputs in memory:

```text
Task A
    TaskResult.output
        ↓
Runner.outputs_by_task_id
        ↓
RunContext.dependency_outputs
        ↓
Task B
```

After process restart:

```text
Runner.outputs_by_task_id
    no longer exists
```

Therefore a correct crash resume cannot merely preserve A as SUCCEEDED and execute B.
It must reconstruct the output boundary durably.

## task_output_checkpoints

M39 introduces a narrow durable checkpoint:

```text
task_output_checkpoints
    task_run_id
    output_json
```

The row is owned one-to-one by TaskRun.

Presence of the row means an output checkpoint exists.

This matters because:

```text
output = None
```

is a valid durable output and must remain distinguishable from:

```text
no durable output checkpoint
```

## Portable output policy

Only strict portable JSON values are checkpointed.

Accepted values reuse the existing serialization boundary:

```text
None
string
boolean
integer
finite float
enum value
mapping with string keys
list / tuple
nested combinations of the above
```

Unsupported Python objects are not:

```text
pickled
repr()-encoded
stringified
silently dropped into arbitrary binary storage
```

An ordinary live run can still use such an in-memory output.

However, if a later crash resume needs that completed task as a dependency, M39 raises
ResumeError because the required context cannot be reconstructed faithfully.

## Atomic success boundary

For a portable output, successful execution now commits together:

```text
TaskAttempt SUCCEEDED
TaskRun SUCCEEDED
TASK_SUCCEEDED event
task output checkpoint
artifact references
external run references
```

inside the same MetadataStore UnitOfWork.

This prevents a committed successful TaskRun from racing ahead of its durable small
output during ordinary execution.

## Alembic revision

M39 adds:

```text
0002_task_output_checkpoints
    ↓
task_output_checkpoints
```

The migration follows `0001_runtime_metadata`.

SQLite and PostgreSQL migration qualification both advance to revision 0002.

## Reconciliation application

M38 is read-only.

M39 is the first recovery milestone allowed to apply M38 decisions.

### CONFIRMED_SUCCEEDED

For one persisted:

```text
TaskRun RUNNING
TaskAttempt RUNNING
```

M39 updates the existing entities to:

```text
TaskRun SUCCEEDED
TaskAttempt SUCCEEDED
```

and emits an ordinary `TASK_SUCCEEDED` event carrying recovery metadata.

It does not create a replacement attempt.

### CONFIRMED_FAILED

M39 converts the existing running attempt to FAILED with stable recovery evidence:

```text
error_type     = ExternalReconciliationFailure
error_category = reconciliation
```

The TaskRun becomes FAILED.

Existing fail-fast propagation is reused for undispatched tasks.

The same WorkflowRun becomes FAILED.

### CONFIRMED_CANCELLED

The existing attempt and task become CANCELLED.

Remaining PENDING/READY tasks are cancelled.

The same WorkflowRun becomes CANCELLED.

### STILL_RUNNING

Resume is rejected.

The external workload still owns active work.

### MANUAL_REQUIRED

Resume is rejected.

PyWorkflowKit does not guess.

## External success and missing Python output

A provider can prove:

```text
external job succeeded
```

but that does not prove what Python value should appear in:

```text
RunContext.dependency_outputs
```

Therefore M39 never fabricates a TaskResult output after external reconciliation.

If no downstream task needs the value, the run may continue/finalize.

If a downstream task requires it, the durable output checkpoint lookup fails and resume
is blocked.

Workloads intended for robust cross-process recovery should prefer durable
ArtifactReference / ExternalRunRef / domain reference identifiers over opaque in-memory
objects.

## PENDING and READY crash boundaries

A crash may occur:

```text
before TASK_READY
    → TaskRun PENDING

after TASK_READY
before TASK_STARTED
    → TaskRun READY
```

M39 supports both.

For PENDING:

- dependency readiness is recalculated;
- dependency output checkpoints are preflighted;
- only then is PENDING → READY persisted.

For READY:

- succeeded upstream dependencies are revalidated;
- the existing READY state is preserved;
- no duplicate TASK_READY event is emitted.

## Attempt numbering

For remaining work:

```text
next attempt number
    =
max(persisted attempt numbers) + 1
```

This preserves monotonically increasing attempt identity across process restarts.

## Event continuity

M39 extends RuntimeEventFactory with:

```text
starting_sequence
```

Resume computes:

```text
max(persisted event_sequence) + 1
```

and continues from there.

Example:

```text
before crash
1 WORKFLOW_STARTED
2 TASK_READY
3 TASK_STARTED

after resume
4 TASK_SUCCEEDED
5 TASK_READY
6 TASK_STARTED
...
```

No separate event stream and no duplicate sequence is created.

## Recovery event vocabulary

M39 does not add recovery-only RuntimeEventType members.

Existing canonical lifecycle events remain authoritative.

Recovery provenance is carried in payload metadata such as:

```json
{"recovery": "resume"}
```

or:

```json
{
  "recovery": "reconciliation",
  "disposition": "confirmed_succeeded"
}
```

This preserves the stable event taxonomy.

## Safety preconditions

Resume rejects:

- workflow identity/version mismatch;
- terminal/non-RUNNING WorkflowRun;
- reconciliation report for a different run;
- MANUAL_REQUIRED reconciliation;
- STILL_RUNNING external work;
- reconciliation TaskRun identity mismatch;
- unexpected TaskRun set;
- inconsistent READY dependencies;
- missing durable dependency output;
- non-resumable persisted task status;
- reconciliation attempt identity mismatch.

## Persistence consistency

Output checkpoints are queryable runtime state.

They do not alter:

```text
RunManifest schema version 1
Plugin API version 1
RuntimeEvent taxonomy
domain lifecycle enum set
```

## Reference acceptance

ACC-RECOVERY-002 now performs:

```text
SQLite process/store A
    WorkflowRun RUNNING
    A SUCCEEDED
    A output checkpoint = {"value": 21}
    B PENDING
        ↓
close store
        ↓
new WorkflowRuntime / new SQLite store
        ↓
M37 stale detection
        ↓
M38 empty reconciliation report
        ↓
M39 resume same run
        ↓
B receives A checkpoint output
        ↓
B executes once
        ↓
same WorkflowRun SUCCEEDED
```

A's handler is intentionally not registered after restart, proving A is not re-executed.

## Out of scope

M39 does not implement:

- automatic/background recovery scanning;
- retry scheduling without sleeping;
- heartbeat/lease ownership;
- distributed recovery locks;
- arbitrary Python object checkpointing;
- exactly-once side effects;
- rerun;
- replay;
- scheduler ownership.

## Next

**M40 — Non-blocking Retry** will replace coordinator sleep-based retry delay with
durable retry eligibility timing while preserving RetryEngine authority.
