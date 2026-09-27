# Compatibility Policy

Status: M41 baseline — 0.7.0a1

## Purpose

PyWorkflowKit is still pre-1.0, but the 0.7-0.9 phase deliberately adopts a stronger
compatibility discipline than the minimum allowed by Semantic Versioning for 0.x
packages.

The objective is to reduce accidental API churn before 1.0.

## Contract classes

### Stable-intent contracts

Changes require explicit compatibility review and reference-test updates:

~~~text
package-root __all__
WorkflowRunStatus
TaskRunStatus
TaskAttemptStatus
RuntimeEventType
MetadataStore
UnitOfWork
CLI command names
CLI documented exit codes
RunManifest schema version
Plugin API version
migration history
~~~

### Advanced/internal surfaces

Advanced module imports remain usable but are not automatically promoted to the same
compatibility tier merely because they exist.

Examples include:

~~~text
ConcurrentRunner
ThreadExecutor
ProcessExecutor
AsyncExecutor
SubprocessExecutor
RecoveryInspector
ReconciliationService
~~~

Their behavior is still tested, but package-root stability is not implied.

## Compatible changes

Normally compatible:

~~~text
bug fixes preserving documented semantics
performance improvements
new optional capabilities
new additive fields where the owning contract explicitly permits them
new advanced-module APIs
new migration revisions that preserve supported upgrade paths
~~~

## Potentially breaking changes

Require explicit review:

~~~text
removing/renaming a package-root symbol
changing enum values
changing RuntimeEvent meaning
removing or changing required MetadataStore/UnitOfWork methods
renaming CLI commands
changing established exit-code meaning
changing machine-readable JSON keys incompatibly
changing Manifest schema without a version transition
changing Plugin API compatibility rules
rewriting migration history
~~~

## Change process

From M41 onward, a change to a stable-intent contract must do one of:

1. preserve compatibility and extend the relevant contract test;
2. introduce a documented deprecation path;
3. explicitly version the affected contract;
4. document a narrowly justified emergency break for security or invariant correctness.

Silent breaking changes are not accepted.

## Pre-1.0 note

This policy does not claim that every internal API is frozen before 1.0.

It establishes a controlled path toward the 1.0 stability review, whose final freeze
still includes top-level exports, exceptions, states/enums, CLI commands/exit codes,
Plugin API, MetadataStore, manifest schema, and configuration schema.


## M43 CLI machine-contract rules

The CLI machine contract is versioned independently as `CLI_MACHINE_CONTRACT_VERSION = "1"`.

Within v1, existing required JSON keys and their meanings are stable-intent contracts.
Backward-compatible additive fields are permitted when they do not change the semantics
of existing keys; consumers should ignore unknown fields.

The following require deprecation or an explicit machine-contract version transition:

~~~text
command removal or rename
application exit-code semantic change
required key removal or rename
incompatible value-type/semantic repurposing
success/error stream reversal
manifest JSON change that bypasses RunManifest schema versioning
~~~

Machine success JSON is written to stdout. Handled JSON errors are written to stderr
and retain the shared `error` + `exit_code` contract.


## M44 plugin ecosystem compatibility rules

Plugin API v1 now has a public conformance surface shared by runtime discovery and
third-party plugin tests.

Stable-intent plugin contracts include:

~~~text
PluginType values
PluginDescriptor field meanings
ENTRY_POINT_GROUPS
PLUGIN_TYPE_BY_ENTRY_POINT_GROUP
RegisteredPlugin provider shape
PLUGIN_API_VERSION exact compatibility rule
PluginContractIssueCode meanings
Executor / MetadataStore / RuntimeEventSink structural instance checks
~~~

Registration validation is side-effect-free: it never invokes the plugin factory.

Third-party authors may explicitly instantiate their plugin and then run instance
conformance. The generic workload category intentionally has no extra runtime Protocol
in Plugin API v1.

Changing these contracts requires the M42 deprecation process where applicable or a
Plugin API version transition.


## M45 persistence and migration compatibility rules

Durable relational persistence now has an explicit schema contract version and frozen
published migration lineage.

The following are stable-intent persistence contracts:

~~~text
PERSISTENCE_SCHEMA_CONTRACT_VERSION
published Alembic revision IDs
published migration source content
linear down_revision ancestry
current migration head for a release
forward upgrade from supported historical revisions
MetadataStore readability after upgrade
current UnitOfWork writability after upgrade
~~~

Published migrations are append-only history. Existing migration files must not be
rewritten after release; schema evolution appends a new revision.

A PyWorkflowKit build rejects databases whose current Alembic revision is not present
in its known migration history. This prevents an older runtime from silently operating
against an unknown/future schema.

The product compatibility promise is forward migration to head. Downgrade compatibility
is not promoted to a stable application-level contract by M45.


## M46 release qualification rules

Compatibility claims are release-qualified from built distribution artifacts, not only
from an editable source checkout.

Release qualification contract v1 freezes:

~~~text
supported Python versions: 3.11 / 3.12 / 3.13
CLI machine contract: 1
RunManifest schema: 1
Plugin API: 1
Persistence schema contract: 1
migration head: 0003_retry_eligible_at
~~~

A release candidate must pass:

~~~text
release metadata consistency
wheel and sdist build
package metadata validation
installed-artifact smoke tests
reference contract snapshots
SQLite upgrade matrix
PostgreSQL upgrade matrix
security gates
~~~

When a qualification run is triggered by a tag, the tag must equal `v<project.version>`.

Release qualification is non-publishing. Passing it does not itself upload to PyPI,
create a GitHub Release, or push a tag.
