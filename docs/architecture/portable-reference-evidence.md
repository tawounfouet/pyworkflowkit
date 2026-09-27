# Portable Reference and Integration Evidence Contract

Status: M48 — 0.8.0a2

## Purpose

M48 hardens `ArtifactReference` and `ExternalRunRef` as portable integration evidence
without turning PyWorkflowKit into an artifact store or a mirror of foreign runtimes.

The contract covers:

~~~text
stable provider naming
foreign identifier preservation
absolute URI semantics
JSON-portable metadata
manifest redaction
deterministic serialization
durable persistence round trips
deterministic lineage projection
~~~

## Contract version

~~~text
REFERENCE_INTEROPERABILITY_CONTRACT_VERSION = "1"
~~~

The dedicated public import path is:

~~~python
from pyworkflowkit.integrations import (
    REFERENCE_INTEROPERABILITY_CONTRACT_VERSION,
    normalize_reference_metadata,
    validate_portable_artifact_reference,
    validate_portable_external_run_ref,
    validate_provider_name,
    validate_reference_uri,
)
~~~

The stable package-root API from 0.7 is unchanged.

## Compatibility strategy

M48 does not retroactively make the historical `ArtifactReference` and
`ExternalRunRef` constructors stricter.

Legacy code can still construct values using the 0.7 domain rules.

The interoperability guarantee is explicit:

~~~text
domain reference
      │
      ▼
M48 portable validation
      │
      ├── pass  → portable interoperability contract applies
      └── fail  → value remains a domain value but has no M48 portability guarantee
~~~

This avoids silently breaking 0.7 applications while giving 0.8 integrations a stronger
contract.

## Stable provider naming

A portable `ExternalRunRef.provider` uses a lowercase stable identifier.

Accepted examples:

~~~text
pyingestkit
acme.jobs
github-actions
vendor_1
provider2
~~~

The syntax is:

~~~text
lowercase alphanumeric segments
separated by ".", "_" or "-"
~~~

Provider values are validated but never normalized.

For example:

~~~text
acme.jobs
~~~

remains exactly `acme.jobs`.

The runtime does not lowercase, rewrite or alias provider identifiers.

## Foreign identifier preservation

`external_run_id` belongs to the foreign runtime.

PyWorkflowKit must preserve it exactly.

Example:

~~~text
CaseSensitive/Foreign-ID:42
~~~

must not become:

~~~text
casesensitive/foreign-id:42
CaseSensitive-Foreign-ID-42
42
~~~

The same rule applies to:

~~~text
artifact_id
external_ref_id
URI spelling
checksum spelling
artifact name
~~~

unless a specific producer creates a new value intentionally.

## URI semantics

Portable artifact references require an absolute URI with a scheme.

Examples:

~~~text
file:///tmp/output.csv
s3://bucket/path/output.csv
https://example.test/artifacts/42
urn:example:artifact:42
memory://artifact/output
~~~

Portable external-run references may omit `uri`.

When present, the URI must also be absolute.

M48 does not require a particular transport or storage vendor.

It does not:

~~~text
open URIs
download artifacts
authenticate to providers
verify remote existence
rewrite URI casing
canonicalize provider URLs
~~~

## Metadata portability

Portable reference metadata must be representable as strict JSON.

Allowed structures are composed from:

~~~text
null
string
boolean
integer
finite float
string-keyed mappings
lists / tuples of portable values
enum values representable by portable values
~~~

Rejected examples include:

~~~text
arbitrary Python objects
non-string mapping keys
NaN
Infinity
custom class instances
~~~

Tuple values normalize to JSON arrays at serialization boundaries.

## Persistence

The existing persistence rows remain unchanged:

~~~text
ArtifactReferenceRow
ExternalRunRefRow
~~~

M48 introduces no new Alembic migration.

SQLite and PostgreSQL continue to store reference metadata using the existing portable
JSON contract.

The identity fields and URIs are round-tripped without rewriting.

## Serialization

The existing strict schemas remain the canonical serialization boundary:

~~~text
ArtifactReferenceSchema
ExternalRunRefSchema
~~~

SchemaCodec continues to produce deterministic canonical JSON.

M48 validation complements those schemas by making the interoperability expectations
explicit before a reference reaches a durable or external boundary.

## Manifest redaction

Reference metadata may contain contextual integration values.

The RunManifest is external-facing evidence and must not expose values whose keys look
sensitive.

M48 applies the existing recursive key-based redaction policy to:

~~~text
artifact metadata
external-run-reference metadata
~~~

Sensitive key examples include:

~~~text
password
secret
token
api_key
authorization
credential
private_key
~~~

Example:

~~~text
{
  "authorization": "Bearer abc",
  "nested": {
    "private_key": "secret",
    "region": "eu"
  }
}
~~~

becomes in the manifest:

~~~text
{
  "authorization": "<redacted>",
  "nested": {
    "private_key": "<redacted>",
    "region": "eu"
  }
}
~~~

The durable metadata store is not rewritten by manifest redaction.

Redaction is an evidence-projection boundary, not an encryption mechanism or secret
manager.

Applications should still avoid placing secrets in reference metadata whenever
possible.

## Manifest ordering

Manifest artifacts and external references remain deterministically sorted by their
PyWorkflowKit reference identifiers.

~~~text
ArtifactReference     → artifact_id
ExternalRunRef        → external_ref_id
~~~

This ensures stable reconstructed evidence independent of persistence insertion order.

## Lineage determinism

M48 extends deterministic ordering to `ExecutionLineage`.

For each TaskRun:

~~~text
attempt_ids       → attempt_number, attempt_id
artifact_ids      → artifact_id
external_ref_ids  → external_ref_id
~~~

The projection therefore does not depend on the order returned by a MetadataStore
implementation.

## Relationship with M47

M47 external workloads now consume the M48 portability contract.

For a new `ExternalWorkloadResult`:

~~~text
provider
URI
metadata
artifacts
~~~

must satisfy the portable reference requirements before the TaskResult crosses the
integration boundary.

This means M47 + M48 now form:

~~~text
foreign runtime
      ↓
ExternalWorkloadResult
      ↓
portable reference validation
      ↓
TaskResult
      ↓
persistence
      ↓
manifest / lineage
~~~

## Artifact ownership

PyWorkflowKit continues to own only artifact references.

It does not become responsible for artifact payload storage.

The following remain external concerns:

~~~text
S3
MinIO
Azure Blob Storage
Google Cloud Storage
filesystem lifecycle
retention
replication
download authorization
content serving
~~~

## External runtime ownership

An `ExternalRunRef` is correlation evidence only.

~~~text
ExternalRunRef != WorkflowRun
ExternalRunRef != TaskRun
ExternalRunRef != TaskAttempt
~~~

PyWorkflowKit does not copy a foreign runtime state machine into its domain.

## Acceptance criteria

M48 is complete when:

~~~text
provider identifiers follow a deterministic portable naming rule
foreign external_run_id values are preserved exactly
portable URIs are explicitly validated
reference metadata is strict JSON-portable
serialization round trips preserve identity and URI
SQLite durable persistence preserves raw evidence
manifest reference metadata is recursively redacted
manifest output contains no tested secret values
lineage ordering is deterministic
M47 consumes the portable reference contract
no database migration is introduced
0.7 package-root compatibility remains intact
~~~

## Non-goals

M48 does not add:

~~~text
artifact payload storage
remote URI resolution
remote existence checks
provider authentication
object-store clients
artifact retention policy
foreign runtime schema mirroring
provider-specific status enums
automatic secret encryption
global provider registry
~~~

## Next

M49 — Observability Interoperability — 0.8.0a3.
