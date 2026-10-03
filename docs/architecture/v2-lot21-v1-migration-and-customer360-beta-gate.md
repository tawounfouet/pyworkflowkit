# PyWorkflowKit V2 — LOT-21 V1 Migration and Customer 360 Beta Gate

## Status

LOT-21 closes the migration-evidence line and qualifies the Customer 360 reference
workflow as the V2 beta gate.

Milestone candidate:

```text
2.0.0b2
```

The lot is deliberately fail-closed. Migration preserves evidence; it does not fabricate
V2 facts that did not exist in the 1.1 model.

## Compatibility decision log

### Generic aliases

Decision:

```text
DO NOT preserve generic V1 names as implicit V2 aliases
```

The frozen 1.1 package root remains the legacy contract. Canonical V2 usage remains on
qualified namespaces such as:

```text
pyworkflowkit.authoring
pyworkflowkit.runtime
pyworkflowkit.persistence
pyworkflowkit.integrations
```

Migration tooling lives only under:

```text
pyworkflowkit._compat
```

Canonical V2 modules must not import `pyworkflowkit._compat`.

### compatibility.py

`pyworkflowkit.compatibility` remains the frozen 1.x release-compatibility surface. It is
not renamed underneath existing consumers.

LOT-21 therefore resolves the migration-ledger `MOVE/SHIM` decision as:

```text
legacy compatibility.py
    -> KEEP for the 1.x facade

V1 -> V2 semantic migration
    -> pyworkflowkit._compat.v1_to_v2

new V2 implementation
    -> MUST NOT import either legacy compatibility implementation
```

### Decorator migration

There is no decorator alias bridge.

A legacy decorator-based workflow must first materialize its legacy
`WorkflowDefinition`; the resulting explicit definition is then passed to the migration
functions.

This avoids executing decorators or handler code during migration.

### Executor migration

The only default executor conversion is explicit and documented:

```text
V1 local
    -> V2 inline
```

Unknown/custom executor keys fail with `PWK-MIG-V1-EXECUTOR` unless the caller supplies
an explicit `executor_map`.

### Recovery migration

V1 runtime evidence does not contain V2:

- definition fingerprint;
- plan fingerprint;
- CorrelationContext;
- external-run TaskAttempt ownership in the ExternalRunRef value;
- reconciliation disposition.

LOT-21 never synthesizes those values.

Recovery/reconciliation can continue as V2 only after the missing identity evidence is
supplied explicitly by the migration caller.

## Authoring migration

The canonical helper is:

```text
pyworkflowkit._compat.v1_to_v2
```

It provides explicit conversions for:

```text
V1 WorkflowDefinition -> V2 WorkflowDefinition
V1 TaskDefinition     -> V2 TaskDefinition
```

A V1 `handler_ref` becomes a V2 `RegisteredWorkload.registry_key`.

The migration is rejected when:

- `handler_ref` is missing;
- V1 workflow-level parameters are present without an explicit redesign;
- V1 HARD timeout would lose its cancellation semantics;
- the executor key has no explicit mapping;
- a legacy retry category has no exact V2 FailureCategory mapping.

No ambiguous generic alias is created.

## Retry-policy migration

The safely equivalent fields map as:

```text
max_attempts              -> max_attempts
backoff_strategy          -> backoff_strategy
delay_seconds             -> initial_delay_seconds
max_delay_seconds         -> max_delay_seconds
known retry category      -> exact FailureCategory
```

V2-only fields keep their canonical defaults.

An unknown legacy retry-category string is not guessed.

## Runtime migration

### WorkflowRun

A V1 WorkflowRun can become a V2 WorkflowRun only when the caller supplies:

```text
definition_fingerprint
plan_fingerprint
CorrelationContext
```

and the legacy record contains `created_at`.

The textual V1 run id is preserved through the typed V2 identifier.

### TaskRun

Task identity, status, timestamps and supported SkipReason values are preserved directly.

A missing legacy `created_at` is insufficient evidence.

### TaskAttempt

The V1 TaskAttempt entity did not store `created_at`.

The migration therefore requires caller-supplied creation evidence.

Legacy fields that do not map safely into V2 `FailureEvidence` remain attached to the
migration result as `LegacyAttemptEvidence`:

```text
retry_eligible_at
error_type
error_message
error_category
error_metadata
```

LOT-21 does not invent retryability, uncertainty or a V2 failure category.

## ExternalRunRef migration

V1 external tracking did not contain a V2 `kind`.

The caller must supply it explicitly.

The V1 fields:

```text
external_ref_id
uri
```

remain available as `LegacyExternalRunEvidence`; they are not silently reinterpreted as
V2 execution semantics.

Non-string V1 metadata is rejected rather than coerced into the stricter V2 portable
metadata contract.

TaskAttempt ownership is never inferred from the V1 value object.

## Semantic metadata export/import

LOT-21 adds `V1RuntimeMetadataSnapshot`.

The snapshot round-trips:

- WorkflowRun;
- TaskRun values;
- TaskAttempt history;
- retry_eligible_at;
- legacy failure strings/metadata;
- ExternalRunRef values.

The canonical JSON envelope fixes:

```text
contract = pyworkflowkit.v1_runtime_metadata
contract_version = 1
external_run_attempt_ownership = null
```

The decoder rejects payloads that try to populate
`external_run_attempt_ownership`, because doing so would invent a fact absent from the
legacy value contract.

The format is data-only and never imports payload-selected Python modules/classes.

## Customer 360 beta topology

The beta application remains:

```text
ingest_customers ─────┐
                      ├── transform_customer_360 ── publish_mart
ingest_orders ─────────┘
```

Ownership remains:

```text
ingestion/publication -> PyIngestKit boundary
transformation        -> PyTransformKit boundary
orchestration/retry   -> PyWorkflowKit
```

## Beta acceptance layers

### Happy path and workflow retry

The installed-artifact qualification executes the complete graph.

The transformation intentionally reports one retryable failure before succeeding.

Expected evidence:

```text
one WorkflowRun
one transform TaskRun
two transform TaskAttempts
two TransformationExecution external refs
one publication external ref
SUCCEEDED workflow
```

### Portable task outputs

Ingestion checkpoints remain JSON data.

The transformation handoff remains the real portable resource contract:

```text
scheme
locator
media_type
metadata
```

### UNKNOWN_OUTCOME and restart

LOT-20 evidence remains inherited by the beta gate:

- transformation uncertainty;
- publication uncertainty;
- SQLite close/reopen;
- same-attempt reconciliation;
- no duplicate sibling execution.

### Lineage traversal

The installed beta workflow projects `ExecutionLineage` after completion.

The gate verifies:

- all four task nodes;
- three DAG dependency edges;
- both transformation attempts;
- all sibling ExternalRunRef values;
- durable output digests for every task.

### Security negative scenario

The installed artifact executes a second workflow where an upstream task returns a
non-portable Python object.

Expected behavior:

```text
PyTransformKit wrapper is never invoked
PWK-PYTRANSFORMKIT-NONPORTABLE-INPUT
workflow FAILED
```

The happy-path gate also verifies that opaque `credential_ref` values are absent from
durable ExternalRunRef metadata.

### Built artifact execution

`.github/workflows/release-qualification.yml` runs:

```text
scripts/qualify_v2_customer360_beta.py
```

after installation from:

```text
wheel: Python 3.11
wheel: Python 3.12
wheel: Python 3.13
sdist: Python 3.13
```

The script runs from `/tmp`, so imports resolve against the installed artifact rather
than the repository package tree.

## Public sibling boundary

The beta qualification imports only the qualified PyWorkflowKit integration surfaces.

The core package remains importable without PyIngestKit or PyTransformKit installed.
Sibling packages are not imported implicitly by the V2 anti-corruption modules.

## Exit criteria

LOT-21 is complete when:

```text
[ ] V1 concept inventory is reconciled
[ ] explicit WorkflowDefinition migration exists
[ ] explicit TaskDefinition migration exists
[ ] runtime migration requires missing V2 evidence instead of inventing it
[ ] retry history preserves TaskAttempt identity and legacy evidence
[ ] ExternalRunRef migration requires explicit kind
[ ] semantic metadata export/import round-trips
[ ] ambiguous external ownership remains explicit
[ ] decorator migration has a documented materialize-then-migrate path
[ ] executor migration decision is explicit
[ ] recovery migration decision is explicit
[ ] compatibility-shim decisions are recorded
[ ] full Customer 360 workflow is green
[ ] workflow retry is green
[ ] publication UNKNOWN_OUTCOME/restart remains green
[ ] lineage traversal is green
[ ] security negative scenario is green
[ ] wheel/sdist installed-artifact execution is green
[ ] sibling integrations remain optional and public-boundary-only
[ ] CI is green
[ ] Release Qualification is green
```
