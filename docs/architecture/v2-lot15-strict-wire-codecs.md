# PyWorkflowKit V2 — LOT-15 Strict Wire Schemas and Versioned Codecs

## Status

LOT-15 finalizes the canonical V2 wire layer for portable boundary values introduced in
LOT-01.

The qualified namespace is:

```text
pyworkflowkit.serialization
```

The frozen 1.1 module:

```text
pyworkflowkit.contracts.serialization
```

remains intact for compatibility.

## Qualified wire contracts

LOT-15 freezes five contract identities:

```text
pykit.correlation_context
pykit.failure_evidence
pyworkflowkit.workflow_execution_reference
pyworkflowkit.external_run_ref
pyworkflowkit.diagnostic
```

All currently use:

```text
contract_version = 1
```

Contract version remains independent from package version.

## Envelope

Every encoded value uses one non-executable envelope:

```json
{
  "contract": "pykit.correlation_context",
  "contract_version": "1",
  "payload": {}
}
```

No type name, import path, Python module path, callable, pickle payload or executable
deserialization hint is accepted.

The contract identity selects a statically registered schema and a statically registered
domain mapper.

## Canonical JSON

BoundaryWireCodec emits deterministic UTF-8 JSON using:

```text
ensure_ascii = false
allow_nan = false
sort_keys = true
separators = (",", ":")
```

Equivalent current-contract values therefore produce byte-stable JSON.

LOT-15 golden fixtures qualify the exact wire representation for all five contract
families.

## Strict decoding

Decoding is fail-closed.

The wire layer rejects:

```text
unknown envelope fields
unknown payload fields
unknown contracts
unsupported versions without an upcaster
duplicate JSON object keys
NaN / Infinity / -Infinity
invalid UTF-8
non-object envelopes
invalid enum values
naive timestamps
primitive coercion through strict schemas
contract-version disagreement inside domain values
```

Pydantic is used only as a strict data-validation layer.

It is not used for dynamic class loading or executable reconstruction.

## Payload limits

Default codec limits are:

```text
max payload bytes   = 1,048,576
max nesting depth   = 32
```

Both are constructor-configurable but fail closed when exceeded.

The byte limit is checked before JSON decoding.

The nesting limit is checked before schema reconstruction and again after upcasting.

## Explicit upcasting

BoundaryUpcasterRegistry owns migration hooks:

```text
(contract, from_version)
        │
        ▼
(to_version, pure mapping transform)
```

An upcaster:

- receives a read-only mapping view;
- must return another mapping;
- cannot select a Python type;
- cannot bypass the target strict schema;
- cannot silently skip unknown version gaps.

Upcaster chains are bounded and cycle-checked.

No historical version is invented by LOT-15. Hooks exist so a later published contract
revision can provide explicit migration from a real prior wire version.

## Domain mapping

LOT-15 maps only these canonical V2 dataclasses:

```text
CorrelationContext
WorkflowExecutionReference
ExternalRunRef
FailureEvidence
Diagnostic
```

The mapping is explicit in both directions.

Pair collections such as:

```text
metadata
details
```

become JSON objects only when their keys are unique. Duplicate domain keys are rejected
instead of being silently overwritten.

Timezone-aware datetimes are emitted in UTC using canonical ISO-8601 with a trailing
`Z`.

## Compatibility aliases

The qualified V2 namespace preserves transitional names:

```python
pyworkflowkit.serialization.SchemaCodec
pyworkflowkit.serialization.StrictSchema
```

but they now point to:

```text
BoundaryWireCodec
StrictBoundarySchema
```

This does not mutate:

```text
pyworkflowkit.contracts.serialization.SchemaCodec
pyworkflowkit.contracts.serialization.StrictSchema
```

which remain part of the frozen 1.1 implementation.

## Golden fixtures

Qualified fixtures live under:

```text
tests/fixtures/v2_serialization/
```

and freeze:

```text
correlation_context_v1.json
workflow_execution_reference_v1.json
external_run_ref_v1.json
failure_evidence_v1.json
diagnostic_v1.json
```

Acceptance requires:

```text
domain value
   ↓ encode
exact golden bytes
   ↓ decode
same canonical domain value
   ↓ encode
same exact golden bytes
```

## Security model

LOT-15 deserialization is data-only.

Explicitly forbidden design directions include:

```text
pickle
cloudpickle
eval
exec
dynamic import from wire data
module/class discriminator loading
implicit string-to-object fallback
```

The wire envelope contains no executable dispatch information.

## Acceptance invariants

LOT-15 proves:

```text
five contract identities remain versioned independently
canonical JSON is deterministic
strict schema extra fields are rejected
primitive coercion is rejected
duplicate JSON keys are rejected
non-finite numbers are rejected
invalid UTF-8 is rejected
payload byte limits are enforced before decode
nesting limits are enforced
unknown contracts fail closed
unknown versions fail without explicit upcaster
upcaster chains are explicit, bounded and cycle-safe
decode_as enforces expected domain type
domain duplicate metadata/details keys are not collapsed
golden fixtures round-trip exactly
1.1 serialization implementation remains untouched
root 1.1 public API remains unchanged
```

## Boundary

LOT-15 does not serialize executable workflow definitions or Python callables.

It also does not yet migrate plugin contracts.

The next roadmap area is:

```text
LOT-16 — Plugin Contract Migration
```
