# Persistence and Migration Compatibility Contract

Status: M45 — 0.7.0a5

## Purpose

M45 turns relational schema evolution into an explicit compatibility contract.

A fresh database reaching the current schema is necessary but not sufficient. A durable
workflow runtime must also preserve databases created by earlier released revisions.

M45 therefore qualifies:

~~~text
historical revision
        ↓
historical data
        ↓
upgrade to current head
        ↓
old data readable by current MetadataStore
        ↓
new current-version writes succeed
~~~

on both SQLite and PostgreSQL.

## Persistence schema contract

~~~text
PERSISTENCE_SCHEMA_CONTRACT_VERSION = "1"
~~~

This contract version is independent from:

~~~text
package version
CLI machine contract
Plugin API
RunManifest schema
~~~

## Frozen migration lineage

The 0.7.0a5 lineage is linear:

~~~text
0001_runtime_metadata
        ↓
0002_task_output_checkpoints
        ↓
0003_retry_eligible_at
        ↓
HEAD
~~~

The current migration head remains:

~~~text
0003_retry_eligible_at
~~~

M45 intentionally adds no schema migration.

## Immutable-history rule

Once a migration has shipped, its source is immutable.

A future schema change must append a new revision:

~~~text
0003_retry_eligible_at
        ↓
0004_...
~~~

It must not edit 0001, 0002, or 0003 in place.

Reference tests freeze the packaged migration order and the Git-blob fingerprint of the
three published migration files.

## Supported upgrade origins

This package explicitly supports opening and upgrading databases at:

~~~text
unversioned / fresh
0001_runtime_metadata
0002_task_output_checkpoints
0003_retry_eligible_at
~~~

A database claiming another revision is rejected before Alembic attempts migration.

This protects against accidentally opening a database produced by a newer or unrelated
schema history with an older PyWorkflowKit runtime.

## Upgrade-target rule

Programmatic upgrade targets are limited to:

~~~text
head
or
one of the packaged known revisions
~~~

Unknown target identifiers are rejected with MigrationCompatibilityError.

## Historical-data qualification

### From 0001

The qualification seeds historical rows for:

~~~text
workflow_runs
task_runs
task_attempts
runtime_events
~~~

then upgrades to head.

The current MetadataStore must reconstruct those domain values successfully, with the
new retry_eligible_at field represented as None for the historical attempt.

### From 0002

The same scenario additionally seeds:

~~~text
task_output_checkpoints
~~~

The checkpoint must survive the upgrade and remain readable through the current
MetadataStore.

## Continued writes

After historical data is migrated, M45 writes a new current-version artifact through
the UnitOfWork API and reads it back.

This demonstrates that the migrated database is not merely inspectable; it remains
writable by the current persistence adapter.

## SQLite and PostgreSQL

The same compatibility semantics apply to both supported durable relational adapters.

PostgreSQL retains its schema boundary:

~~~text
pyworkflowkit.*
~~~

and UUID / JSONB / TIMESTAMPTZ physical types.

SQLite continues to use its translated no-schema layout.

## Downgrades

M45 does not promise application-level downgrade compatibility.

Alembic downgrade functions remain implementation tooling, but the product compatibility
promise is forward migration from supported historical revisions to the current head.

## Compatibility policy

Stable-intent persistence contracts include:

~~~text
published migration files and revision IDs
linear down_revision ancestry
migration head identity for a release
MetadataStore / UnitOfWork semantics
ability to read historical durable records after supported upgrades
~~~

Changing a published migration in place is prohibited.

A future intentional incompatibility requires an explicit migration path, release note,
and compatibility policy update rather than silent schema replacement.

## Scope boundary

M45 does not add:

~~~text
new tables
new columns
data-retention policy
database backup tooling
cross-database replication
automatic downgrade support
online zero-downtime DDL guarantees
~~~

## Next

M46 — Release Automation and Upgrade Matrix.
