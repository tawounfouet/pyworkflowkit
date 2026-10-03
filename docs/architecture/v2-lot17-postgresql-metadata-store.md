# PyWorkflowKit V2 — LOT-17 PostgreSQL MetadataStore

## Status

LOT-17 introduces the canonical V2 PostgreSQL persistence adapter:

```text
pyworkflowkit.persistence.PostgreSQLMetadataStore
```

It completes the first V2 relational backend pair:

```text
MetadataStore V2
    ├── InMemoryMetadataStore
    ├── SQLiteMetadataStore
    └── PostgreSQLMetadataStore
```

## Architectural decision

LOT-17 does not create a new persistence model.

LOT-10 already established the canonical relational V2 semantics and migrations:

```text
0004_v2_runtime_metadata
0005_v2_task_output_checkpoints
```

Those migrations are already PostgreSQL-aware and create their objects in the
`pyworkflowkit` schema.

LOT-17 therefore adds an adapter, not an artificial schema revision.

## Canonical PostgreSQL settings

`PostgreSQLSettings` owns:

```text
dsn
pool_size
max_overflow
application_name
```

The engine contract is:

```text
PostgreSQL SQLAlchemy URL only
READ COMMITTED
pool_pre_ping = true
UTF-8 client encoding
UTC session timezone
bounded SQLAlchemy pool
application_name = pyworkflowkit-v2
```

## Behavioral equivalence

The PostgreSQL implementation runs the same reusable
`MetadataStoreContractSuite` as Memory and SQLite.

The suite proves:

```text
runtime-checkable MetadataStore conformance
WorkflowRun round trip
duplicate identity rejection
compare-and-set updates
immutable identity protection
append-only transition evidence
TaskRun ownership
contiguous TaskAttempt history
conditional attempt updates
attempt-scoped ExternalRunRef
unfinished-run query semantics
RuntimeEvent projection
portable output checkpoints
manifest reference idempotency
```

## PostgreSQL-specific evidence

LOT-17 additionally proves:

```text
two independent store instances see the same durable state
stale multi-writer compare-and-set is rejected
READ COMMITTED is active
UTC session timezone is active
UTF-8 client encoding is active
application_name is explicit
migration head is 0005_v2_task_output_checkpoints
```

## Concurrency posture

PostgreSQL is a shared durable backend.

`supports_concurrent_writers = true` means multiple runtime processes may safely
coordinate through database constraints and compare-and-set state writes.

It does not mean PyWorkflowKit owns:

```text
distributed scheduling
worker leasing
global locks
leader election
exactly-once external effects
```

Those remain separate concerns.

## Transaction posture

LOT-17 preserves the current V2 stable MetadataStore contract:

```text
supports_atomic_batch = false
```

Individual store operations are transactional.

A public multi-operation UnitOfWork is not promoted merely because PostgreSQL supports
transactions. Such a surface requires an explicit V2 contract decision.

## Compatibility

The historical adapter remains available from:

```text
pyworkflowkit.adapters.metadata.postgres.PostgresMetadataStore
```

LOT-17 does not rename or reinterpret that 1.1 contract.

The canonical V2 adapter is intentionally named:

```text
PostgreSQLMetadataStore
```

and lives only under the qualified V2 persistence surface.

## Migration policy

No `0006` migration is introduced.

This is deliberate:

```text
new adapter
    !=
new schema
```

The existing append-only migration lineage remains authoritative.

## Qualification

CI PostgreSQL qualification now runs:

```text
legacy PostgreSQL integration contract
migration/upgrade contract
V2 PostgreSQL MetadataStore contract
```

Release qualification runs the V2 PostgreSQL contract on Python 3.11, 3.12 and 3.13
alongside the PostgreSQL migration matrix.

## Exit criteria

LOT-17 is complete when:

```text
[ ] PostgreSQLMetadataStore exists
[ ] PostgreSQLSettings exists
[ ] canonical persistence surface exports both
[ ] no package-root promotion occurs
[ ] V2 migration lineage remains unchanged
[ ] full MetadataStoreContractSuite passes against PostgreSQL
[ ] multi-store stale compare-and-set is rejected
[ ] READ COMMITTED / UTC / UTF-8 session contract is proven
[ ] CI is green
[ ] Release Qualification is green
```
