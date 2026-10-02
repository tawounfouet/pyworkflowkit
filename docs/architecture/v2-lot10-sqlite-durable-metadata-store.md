# PyWorkflowKit V2 — LOT-10 SQLite Durable MetadataStore

## Status

Implemented on top of LOT-09.

LOT-10 makes canonical V2 runtime evidence survive process termination and store
recreation.

## Persistence boundary

The canonical qualified V2 persistence surface is now:

```text
pyworkflowkit.persistence.MetadataStore
├── InMemoryMetadataStore
└── SQLiteMetadataStore
```

The frozen package root remains unchanged.

## Append-only migration strategy

The published relational migration history is extended rather than rewritten:

```text
0001_runtime_metadata
        ↓
0002_task_output_checkpoints
        ↓
0003_retry_eligible_at
        ↓
0004_v2_runtime_metadata
```

Revisions 0001–0003 remain byte-for-byte immutable.

Revision 0004 adds dedicated V2 tables:

```text
v2_workflow_runs
v2_task_runs
v2_task_attempts
v2_external_run_refs
v2_state_transitions
v2_manifest_references
```

Legacy 1.1 tables are not reinterpreted or repurposed.

## Durable entities

SQLite persists the canonical LOT-04/05/09 model:

```text
WorkflowRun
  │
  └── TaskRun
        │
        └── TaskAttempt
              │
              └── ExternalRunRef
```

It also persists:

- append-only state transition evidence;
- ManifestReference hooks;
- CorrelationContext;
- FailureEvidence;
- UNKNOWN_OUTCOME and REQUIRES_RECONCILIATION state;
- attempt-scoped external execution identity.

## Failure evidence

FailureEvidence is serialized as structured portable JSON rather than as an exception
pickle.

This includes:

```text
error_code
category
retryability
uncertainty
correlation_id
workflow/task/attempt identifiers
external_run
provider_code
message_summary
occurred_at
details
contract_version
```

ExternalRunRef metadata preserves tuple-pair ordering rather than being flattened into a
mapping.

## Transaction semantics

Every MetadataStore method is one database transaction.

A state-changing update performs a compare-and-set on the persisted status:

```text
WHERE entity_id = ?
  AND status = expected_status
```

The state row and corresponding StateTransitionRecord are committed in the same
transaction.

This prevents blind last-write-wins updates across concurrent SQLite writers.

## Restart guarantee

LOT-10 acceptance proves:

```text
process A
   │
   ├── WorkflowRun = UNKNOWN_OUTCOME
   ├── TaskRun = UNKNOWN_OUTCOME
   ├── TaskAttempt = REQUIRES_RECONCILIATION
   ├── ExternalRunRef = REMOTE-42
   ├── FailureEvidence persisted
   └── close SQLite store
             │
             ▼
       process/store recreation
             │
             ▼
process B
   │
   ├── same run identity
   ├── same attempt identity
   ├── same UNKNOWN_OUTCOME
   ├── same ExternalRunRef
   ├── same transition history
   └── same manifest reference
```

LOT-10 does not yet reconcile the external provider. It only guarantees that the
evidence required to do so survives restart.

## Store metadata

The SQLite adapter reports:

```text
durable = true
supports_concurrent_writers = true
supports_atomic_batch = false
schema_version = current Alembic revision
```

The V2 MetadataStore protocol remains contract version 1 because LOT-10 adds an adapter;
it does not change the protocol methods introduced by LOT-05.

## Next lot

```text
LOT-11 — Recovery and Reconciliation
```

LOT-11 can now discover unfinished durable WorkflowRuns after restart, inspect the last
TaskAttempt and its ExternalRunRef, query the external provider, and resolve
UNKNOWN_OUTCOME without inventing execution facts.
