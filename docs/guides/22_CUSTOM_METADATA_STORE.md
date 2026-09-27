# 22 — Custom Metadata Store

## What you will learn

You will understand how to provide a custom persistence backend without changing workflow
semantics.

## Public contracts

Use:

```python
from pyworkflowkit.ecosystem import MetadataStore, UnitOfWork
```

A custom backend must preserve the same observable semantics as memory, SQLite, and
PostgreSQL.

## Required responsibility

The metadata layer must support persisted runtime state and evidence:

```text
WorkflowRun
TaskRun
TaskAttempt
RuntimeEvent
ArtifactReference
ExternalRunRef
transaction boundary
```

It must not become the DAG validator, retry engine, state machine, or scheduler.

## Unit of Work

The transactional contract protects invariants such as:

```text
state transition
      +
corresponding RuntimeEvent
      ↓
commit together
```

A backend may use very different physical storage internally while preserving that semantic
boundary.

## Adapter design rule

Keep database/client-specific objects on the adapter side. Do not leak sessions, cursors,
ORM rows, or vendor-specific transactions into domain entities.

## Testing

Before shipping a custom metadata plugin, test it against the metadata-store contract and
ecosystem conformance surface.

## Related example

A canonical custom store example is planned in DX04 as
`examples/22_custom_metadata_store.py` if retained in the final example topology.

## Next chapter

Continue with [23 — Control Plane](23_CONTROL_PLANE.md).
