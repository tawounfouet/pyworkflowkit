# PyWorkflowKit V2 — LOT-05 In-Memory MetadataStore

Status: implementation baseline  
Target milestone: `2.0.0a1`  
Depends on: LOT-00 → LOT-04

## Purpose

LOT-05 introduces the canonical V2 persistence port and its deterministic process-local
reference implementation.

The persistence boundary is now:

```text
WorkflowRun
TaskRun
TaskAttempt
ExternalRunRef
        │
        ▼
MetadataStore
        │
        ▼
InMemoryMetadataStore
```

The domain decides legal state transitions.

The store decides how canonical runtime facts are protected and persisted.

## Canonical public surface

```python
from pyworkflowkit.persistence import (
    InMemoryMetadataStore,
    ManifestReference,
    MetadataStore,
    MetadataStoreMetadata,
    StateEntityType,
    StateTransitionRecord,
)
```

Legacy 1.1 stores remain available only through explicit `Legacy*` aliases in the
qualified migration namespace.

The frozen package root is unchanged.

## MetadataStore contract

The V2 Protocol exposes:

```text
metadata()

create_workflow_run()
get_workflow_run()
update_workflow_run()
list_workflow_runs()
list_unfinished_workflow_runs()

create_task_run()
get_task_run()
update_task_run()
list_task_runs()

append_task_attempt()
get_task_attempt()
update_task_attempt()
list_task_attempts()

append_external_run_ref()
list_external_run_refs()

list_state_transitions()

set_manifest_reference()
get_manifest_reference()
```

The contract version is:

```text
V2_METADATA_STORE_CONTRACT_VERSION = "1"
```

## Creation semantics

New runtime identities enter persistence only from their canonical initial states:

```text
WorkflowRun  → PENDING
TaskRun      → PENDING
TaskAttempt  → PENDING
```

The store rejects creation of an identity already carrying later runtime state.

This keeps creation evidence and transition history unambiguous.

## Conditional state updates

The V2 store does not expose blind `save_*` replacement.

Instead:

```python
metadata.update_workflow_run(
    run,
    expected_status=WorkflowRunStatus.RUNNING,
    transitioned_at=now,
)
```

implements compare-and-set semantics:

```text
persisted status
      │
      ├── equals expected_status
      │       ↓
      │   accept replacement
      │
      └── differs
              ↓
      MetadataConflictError
```

The same rule applies to TaskRun and TaskAttempt.

## Domain versus persistence authority

The store deliberately does not duplicate the state-machine transition graph.

Correct flow:

```text
load persisted entity
        ↓
state-machine validates transition
        ↓
entity obtains new valid state
        ↓
MetadataStore CAS update
        ↓
append transition evidence
```

Therefore:

```text
StateMachine
    decides whether PENDING → RUNNING is legal

MetadataStore
    proves persisted state was still PENDING
    when the update was committed
```

This preserves the architecture rule:

```text
domain decides WHAT
store decides HOW
```

## Immutable identity protection

A conditional update may change runtime state, timestamps and failure evidence.

It may not silently change identity-defining fields.

WorkflowRun protects:

```text
run_id
workflow_name
workflow_version
definition_fingerprint
plan_fingerprint
correlation
created_at
```

TaskRun protects:

```text
task_run_id
workflow_run_id
task_key
created_at
```

TaskAttempt protects:

```text
attempt_id
task_run_id
attempt_number
created_at
```

Violations raise:

```text
MetadataInvariantError
```

## State transition history

Every entity creation and every persisted status change creates immutable evidence:

```text
StateTransitionRecord
├── sequence
├── entity_type
├── entity_id
├── from_status
├── to_status
└── occurred_at
```

Example:

```text
1  WorkflowRun W-1  None     → PENDING
2  TaskRun TR-1     None     → PENDING
3  TaskAttempt TA-1 None     → PENDING
4  WorkflowRun W-1  PENDING  → RUNNING
```

Sequence ordering is deterministic inside one store instance.

## Attempt history

TaskAttempt history is append-oriented.

For one TaskRun:

```text
attempt_number = 1
attempt_number = 2
attempt_number = 3
...
```

The store rejects gaps and duplicate identities.

It preserves ascending attempt-number query order.

Retry authorization remains owned by LOT-07 and runtime logic; the store only preserves
the resulting history.

## ExternalRunRef persistence

External execution references are associated with the concrete TaskAttempt:

```text
TaskRun
    └── TaskAttempt
            ├── ExternalRunRef #1
            └── ExternalRunRef #2
```

This is intentionally different from broad TaskRun ownership.

The same external reference cannot be duplicated for one TaskAttempt.

Reference ordering is deterministic by provider, kind and external run identity.

## Unfinished-run discovery

`list_unfinished_workflow_runs()` returns all runs not in absorbing terminal states.

Therefore candidates include:

```text
PENDING
RUNNING
CANCELLATION_REQUESTED
UNKNOWN_OUTCOME
```

while excluding:

```text
SUCCEEDED
FAILED
CANCELLED
TIMED_OUT
```

LOT-11 will use this primitive for recovery/reconciliation discovery.

## Manifest reference hook

LOT-05 does not implement the V2 manifest model.

It only provides a provisional hook:

```text
ManifestReference
├── locator
├── schema_version
└── digest?
```

A persisted manifest reference is idempotent when identical.

A different replacement is rejected rather than using last-write-wins.

The canonical manifest contract remains owned by LOT-12.

## Store metadata

`metadata()` reports:

```text
contract_version
schema_version
durable
supports_concurrent_writers
supports_atomic_batch
```

For the reference memory adapter:

```text
contract_version             = 1
schema_version               = 1
durable                      = false
supports_concurrent_writers  = true
supports_atomic_batch        = false
```

Concurrent writers means multiple threads using the same in-memory store instance.

It does not mean multi-process safety.

## Thread/process/crash semantics

InMemoryMetadataStore uses a re-entrant lock around each operation.

It guarantees atomicity of one MetadataStore method call within one process.

It does not guarantee:

```text
process-to-process coordination
crash recovery
durable fsync semantics
transactional multi-method batches
database-level isolation
```

Those capabilities belong to later durable adapters.

## Defensive copies

Mutable runtime entities are copied on write and copied on read.

Therefore mutating a loaded entity does not mutate persisted state until an explicit
conditional update succeeds.

Immutable boundary values such as ExternalRunRef and ManifestReference may be safely
retained directly.

## Errors

LOT-05 introduces:

```text
MetadataConflictError
    stale expected-status / conflicting persisted reference

MetadataInvariantError
    structural identity/history violation
```

Existing V1 persistence errors remain available where compatible:

```text
MetadataNotFoundError
DuplicateMetadataError
MetadataStoreError
```

## Reusable conformance suite

The reusable contract suite validates:

```text
Protocol conformance
identity preservation
defensive copies
duplicate rejection
conditional updates
stale-write rejection
immutable identity protection
state history
attempt ordering
attempt-number gap rejection
ExternalRunRef persistence
unfinished-run discovery
manifest-reference behavior
```

LOT-10 SQLiteMetadataStore and LOT-17 PostgreSQLMetadataStore are expected to run the
same behavioral suite, augmented with durability/concurrency-specific tests.

## No UnitOfWork in the V2 stable contract yet

PyWorkflowKit 1.1 contains a UnitOfWork abstraction and it remains valuable
implementation evidence.

LOT-05 intentionally freezes only the smallest persistence contract needed for V2
runtime semantics.

The current memory adapter therefore declares:

```text
supports_atomic_batch = false
```

If LOT-06 demonstrates that multi-entity atomic runtime boundaries are mandatory for the
stable V2 port, the transaction surface will be added deliberately before the 2.0 API
freeze rather than inherited implicitly from V1.

## LOT-05 invariants

```text
persistence
    ≠ business transition authority

critical update
    = compare-and-set

last-write-wins
    = forbidden for runtime status

state history
    = append-only evidence

TaskAttempt history
    = ordered and identity-preserving

ExternalRunRef
    = TaskAttempt-scoped

InMemoryMetadataStore
    = deterministic + process-local

durable recovery
    = not claimed
```

## Exit criteria

LOT-05 is complete when:

```text
[ ] MetadataStore Protocol exists
[ ] InMemoryMetadataStore satisfies Protocol
[ ] WorkflowRun CRUD semantics exist
[ ] TaskRun CRUD semantics exist
[ ] TaskAttempt append/read/update semantics exist
[ ] initial persisted states are constrained
[ ] conditional updates reject stale expected status
[ ] immutable identity fields cannot be overwritten
[ ] state history is queryable
[ ] attempt ordering is deterministic
[ ] attempt-number gaps are rejected
[ ] ExternalRunRef persists per TaskAttempt
[ ] unfinished WorkflowRun query exists
[ ] manifest reference hook exists
[ ] contract/schema metadata is inspectable
[ ] conformance suite is reusable
[ ] in-memory implementation is deterministic
[ ] root 1.1 API freeze remains green
[ ] full CI and release qualification pass
```

## Next lot

```text
LOT-06 — InlineExecutor and WorkflowRuntime MVP
```

LOT-06 will combine:

```text
WorkflowDefinition
    ↓
WorkflowPlanner
    ↓
ExecutionPlan
    ↓
WorkflowRuntime
    ├── state machines
    ├── InMemoryMetadataStore
    └── InlineExecutor
```

to produce the first end-to-end PyWorkflowKit V2 execution path.
