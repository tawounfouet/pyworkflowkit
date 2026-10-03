# PyWorkflowKit V2 — LOT-15 Strict Serialization and Versioned Codecs

## Status

LOT-15 replaces the transitional V2 serialization facade with canonical strict boundary
schemas, deterministic JSON codecs, explicit domain/schema mappers, versioned envelopes,
directed migration hooks and golden wire fixtures.

## Architectural rule

PyWorkflowKit keeps one domain model and several technical representations:

```text
Domain dataclasses
      │
      ├── explicit mapper ──► Pydantic boundary schema
      │                            │
      │                            ▼
      │                     canonical JSON
      │
      └── persistence mapper ──► SQLAlchemy row
```

Canonical runtime/domain modules do not import Pydantic.

## Strict schemas

LOT-15 owns the canonical V2 boundary schemas for:

```text
CorrelationContext
WorkflowExecutionReference
ExternalRunRef
FailureEvidence
Diagnostic
RuntimeEvent
TaskOutputCheckpoint
RunManifest
```

Nested manifest task and attempt schemas are part of the RunManifest contract.

The schema baseline is:

```text
extra = forbid
frozen = true
strict = true
```

Unknown fields are rejected.

## Canonical JSON

`SchemaCodec` and `canonical_json()` provide deterministic JSON:

```text
UTF-8
sorted object keys
compact separators
ensure_ascii = false
allow_nan = false
no implicit object-to-string fallback
```

Timestamps are normalized to UTC ISO-8601 with a trailing `Z`.

Mappings require string JSON object keys and finite numbers.

## Versioned envelope

Every portable boundary value is encoded inside:

```json
{
  "contract": "pyworkflowkit.runtime_event",
  "contract_version": "1",
  "payload": {}
}
```

Contract identity is separate from the Python class name.

The current registry contains:

```text
pykit.correlation_context
pykit.failure_evidence
pyworkflowkit.diagnostic
pyworkflowkit.external_run_ref
pyworkflowkit.workflow_execution_reference
pyworkflowkit.runtime_event
pyworkflowkit.task_output_checkpoint
pyworkflowkit.run_manifest
```

## BoundaryCodec

`BoundaryCodec` maps:

```text
domain
  ↓
schema
  ↓
WireEnvelope
  ↓
canonical JSON
```

and reverses the path on decode.

The default maximum wire size is 1 MiB. Oversized payloads fail before schema decoding.

Invalid UTF-8, malformed envelopes, unknown contracts and invalid payloads fail closed.

## Contract versions

Contract versions are independent per contract family.

A payload carrying an embedded `contract_version` must agree with the envelope version.
Version drift is rejected rather than silently normalized.

## Migration model

`WireMigrationRegistry` is a directed graph of explicitly registered upcasters.

```text
v1 --registered--> v2 --registered--> v3
```

No reverse edge is generated automatically.

Therefore:

```text
registered migration       → allowed
unknown future version     → rejected
missing migration path     → rejected
implicit downgrade         → rejected
```

Migration functions operate only on detached JSON dictionaries. Deserialization never
imports or executes a class named by the payload.

## Golden fixtures

LOT-15 freezes byte-for-byte canonical fixtures for all eight portable contracts under:

```text
tests/fixtures/v2/serialization/
```

Reference acceptance proves:

```text
domain → bytes == golden fixture
golden fixture → domain → bytes == same fixture
```

This detects accidental key ordering, timestamp, enum, default-field and envelope drift.

## Roundtrip contract

For every canonical portable value:

```text
domain
  → schema
  → canonical wire
  → schema
  → domain
```

must preserve semantic content.

RunManifest timestamps are canonicalized on the wire; equivalent offsets become UTC `Z`.

## Security boundary

LOT-15 deserialization is data-only.

It does not:

```text
pickle
eval
exec
dynamic import from payload
instantiate arbitrary payload-selected classes
```

ProcessExecutor pickle transport from LOT-14 is a separate trusted intra-runtime boundary
and is not used by the public wire codec.

## Compatibility

The frozen PyWorkflowKit 1.1 root remains unchanged.

Legacy schemas remain available from their historical
`pyworkflowkit.contracts.serialization` module for 1.1 compatibility, but
`pyworkflowkit.serialization` now owns the canonical V2 implementation.

## Acceptance invariants

LOT-15 proves:

```text
Pydantic absent from canonical domain modules
extra fields rejected
strict scalar validation
timezone-aware canonical UTC timestamps
finite JSON only
string mapping keys only
deterministic UTF-8 bytes
bounded payload size
unknown contract rejection
unknown version rejection
explicit multi-hop migration
no implicit downgrade
embedded/envelope version consistency
eight domain/wire roundtrips
eight byte-for-byte golden fixtures
frozen 1.1 root unchanged
```

## Next

LOT-16 owns plugin migration and adaptation to the finalized V2 executor, persistence and
serialization contracts.
