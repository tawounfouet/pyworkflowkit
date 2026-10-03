# PyWorkflowKit V2 — LOT-12 Events, Manifest, Lineage and Durable Outputs

## Status

Implemented on top of LOT-11 recovery/reconciliation and LOT-10 durable runtime state.

LOT-12 closes the V2 execution-evidence model without creating duplicate sources of
truth.

## Evidence authority

The durable authority remains:

```text
WorkflowRun / TaskRun / TaskAttempt
        │
        ├── StateTransitionRecord
        ├── ExternalRunRef
        └── TaskOutputCheckpoint
```

Runtime events, manifests, lineage and inspection are deterministic projections of those
facts.

## Runtime events

V2 `RuntimeEvent` is not stored in a second event table.

Instead:

```text
state transition committed
        │
        ▼
StateTransitionRecord
        │
        ▼
RuntimeEvent projection
```

This prevents a split-brain failure where state is committed but a separately persisted
event is lost.

Canonical event facts are semantic rather than generic state-change wrappers:

```text
WORKFLOW_STARTED
WORKFLOW_RESUMED
WORKFLOW_SUCCEEDED
WORKFLOW_FAILED
WORKFLOW_CANCELLATION_REQUESTED
WORKFLOW_CANCELLED
WORKFLOW_TIMED_OUT
WORKFLOW_UNKNOWN_OUTCOME

TASK_READY
TASK_STARTED
TASK_RETRYING
TASK_SUCCEEDED
TASK_FAILED
TASK_SKIPPED
TASK_CANCELLED
TASK_TIMED_OUT
TASK_BLOCKED
TASK_UNKNOWN_OUTCOME
```

Initial persistence rows such as `PENDING` are not exposed as runtime events. A retry
is projected when Attempt N+1 is created while the logical TaskRun remains the same.
The event sequence is the durable state-transition sequence; gaps are valid because not
every persistence transition is a public runtime fact.

## Durable output policy

Successful task outputs are checkpointed only when they can be represented as strict,
finite, portable JSON.

Portable examples include:

```text
null
string
boolean
integer
finite float
array / tuple
string-keyed object
enum values reducible to JSON
```

Unsupported Python objects are never pickled or represented as fake durable state.

For a non-portable output:

```text
process-local WorkflowResult.output  ✅
durable TaskOutputCheckpoint         ❌
PWK-OUTPUT-NONPORTABLE diagnostic    ✅
```

Each durable output checkpoint records:

```text
task_run_id
output
recorded_at
sha256 canonical JSON digest
```

The checkpoint is immutable/idempotent. A different replacement is rejected.

## Persistence contract v2

The canonical V2 MetadataStore contract is advanced to version 2 with:

```text
list_runtime_events()
set_task_output_checkpoint()
get_task_output_checkpoint()
```

Existing LOT-05 through LOT-11 methods remain unchanged.

## Migration 0005

Migration history is extended append-only:

```text
0001_runtime_metadata
        ↓
0002_task_output_checkpoints
        ↓
0003_retry_eligible_at
        ↓
0004_v2_runtime_metadata
        ↓
0005_v2_task_output_checkpoints
```

Revision 0005 adds only:

```text
v2_task_output_checkpoints
```

No V2 event table is added because `v2_state_transitions` already contains the atomic
event source.

## V2 manifest

The qualified V2 manifest schema is version 2.

It is intentionally separate from the frozen legacy 1.1 manifest schema version 1.

`RunManifestBuilder` reconstructs:

- workflow identity and fingerprints;
- durable workflow status and timestamps;
- task status;
- attempt identity and status;
- attempt-scoped external executions;
- portable durable outputs and their digests.

The manifest intentionally does not embed the event log: events answer what happened,
while the manifest remains the compact final summary. It can be built from reopened
durable storage without executing workload code.

Strict Pydantic/wire serialization remains owned by LOT-15.

## Execution lineage

`ExecutionLineageProjector` requires a V2 WorkflowDefinition or ExecutionPlan and
verifies that its workflow identity, definition fingerprint and plan fingerprint exactly
match the persisted WorkflowRun.

Lineage contains:

```text
WorkflowRun
   │
   ├── TaskRun
   │     ├── TaskAttempt*
   │     ├── ExternalRunRef*
   │     └── output digest?
   │
   └── dependency edges between TaskRun identities
```

Lineage is a projection. No graph database or duplicate graph persistence is introduced.

## Runtime inspection

The qualified `pyworkflowkit.diagnostics` surface now owns the V2 RuntimeInspector.

Inspection reports:

- task status;
- attempt count;
- upstream task keys;
- external execution count;
- durable output availability;
- runtime event count;
- ready and blocked tasks;
- deadlock classification.

The former 1.1 inspection implementation is no longer the canonical qualified V2
implementation.

## WorkflowRuntime facade

The V2 WorkflowRuntime exposes:

```python
runtime.events(run_id)
runtime.manifest(run_id, require_terminal=False)
runtime.lineage(workflow_or_plan, run_id)
runtime.inspect(workflow_or_plan, run_id)
```

These APIs are read-only projections over durable evidence.

## Restart guarantee

SQLite acceptance proves:

```text
process A
  ├── executes workflow
  ├── persists state transitions
  ├── persists portable outputs
  └── closes store
          │
          ▼
       SQLite
          │
          ▼
process B
  ├── reopens store
  ├── events()   == process A
  ├── manifest() == process A
  └── lineage()  == process A
```

No workload re-execution is needed to reconstruct evidence.

## Explicit non-goals

LOT-12 does not add:

- pickle-based arbitrary output persistence;
- a duplicate runtime-event table;
- graph persistence;
- OpenTelemetry ownership;
- strict wire/Pydantic schemas;
- advanced executor adapters;
- plugin/event-sink migration.

Those remain separate later contracts.

## Next implementation area

According to the V2 architecture baseline, executor adapters beyond InlineExecutor are
owned by LOT-13/14. LOT-15 owns strict schemas/codecs and LOT-16 owns plugin migration.
