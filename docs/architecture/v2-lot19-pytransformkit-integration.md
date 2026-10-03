# PyWorkflowKit V2 — LOT-19 PyTransformKit Integration

## Status

LOT-19 introduces the canonical dependency-free V2 anti-corruption boundary between
PyWorkflowKit and PyTransformKit.

```text
PyWorkflowKit
    does not import
PyTransformKit
```

A concrete sibling adapter implements a small protocol and is registered through the
LOT-16 V2 workload-binding contract.

## Ownership boundary

```text
PyWorkflowKit
    owns DAG ordering
    owns TaskRun / TaskAttempt identity
    owns workload-level retry and recovery
    owns durable orchestration evidence

PyTransformKit
    owns transformation-plan semantics
    owns transformation execution
    owns engine/provider retry
    owns transformation resource semantics
```

One PyWorkflowKit task represents one complete PyTransformKit transformation plan.
PyWorkflowKit does not reproduce transform operators, schemas, expressions, engines,
provider retry internals or physical handles.

## Alignment with the sibling runtime

LOT-19 mirrors the current public PyTransformKit runtime semantics without importing the
package.

The sibling exposes:

```text
TransformationExecutionId
ExecutionStatus
TransformationResult
ResourceReference(
    scheme,
    locator,
    media_type?,
    metadata,
)
```

and keeps workload/task retry outside TransformationRuntime ownership.

LOT-19 therefore fixes the cross-framework retry boundary as:

```text
workload retry     -> PyWorkflowKit
provider retry     -> PyTransformKit
```

There is no PyTransformKit-owned workflow retry mode.

## Portable workload declaration

`PyTransformKitWorkload` is a specialized `RegisteredWorkload`.

Its canonical registry key is:

```text
pytransformkit:<plan_ref>
```

The descriptor records:

```text
plan_ref
engine
parameters
credential_ref?
executor_key
contract_version
```

and exposes:

```text
integration_key = "pytransformkit"
```

so the existing planner records the sibling requirement while existing executors continue
to use the normal registered-workload resolution path.

## Input handoff

Transformation inputs come from upstream
`TaskExecutionContext.dependency_outputs`.

Every dependency output is normalized through the canonical strict JSON portability
boundary before sibling execution:

```text
dependency output
      ↓
normalize_json_value
      ↓
plain_json_value
      ↓
PyTransformKitExecutionJob.run(inputs=...)
```

A process-local object therefore fails closed before the sibling wrapper is invoked.

No DataFrame, ORM entity, active provider handle or arbitrary Python object is required
for restart/recovery.

## ResourceReference boundary

LOT-19 defines `PyTransformKitResourceReference` as a dependency-free mirror of the
portable sibling shape:

```text
scheme
locator
media_type?
metadata
contract_version
```

Its checkpoint representation is:

```text
{
  "kind": "pytransformkit.resource_reference",
  "scheme": ...,
  "locator": ...,
  "media_type": ...,
  "metadata": ...,
  "contract_version": "1"
}
```

This value is data-only and can cross persistence/process boundaries.

## Normalized transformation result

The sibling wrapper returns `PyTransformKitExecutionResult` with:

```text
transformation_execution_id
status
resource?
engine_id?
plan_fingerprint?
status_locator?
metadata
error_code?
provider_code?
message_summary?
retryable
```

Supported terminal statuses mirror the sibling lifecycle:

```text
SUCCEEDED
FAILED
CANCELLED
TIMED_OUT
UNKNOWN_OUTCOME
REQUIRES_RECONCILIATION
```

The transformation execution identity is projected into:

```text
ExternalRunRef(
    provider="pytransformkit",
    kind="transformation_execution",
    external_run_id=<TransformationExecutionId>,
)
```

## Success mapping

```text
TransformationExecution SUCCEEDED
        ↓
PyTransformKitResourceReference
        ↓
portable TaskOutputCheckpoint
        +
ExternalRunRef
```

## Confirmed failure mapping

A known failed transformation maps to:

```text
FailureEvidence(
    category=EXTERNAL_PROVIDER,
    uncertainty=KNOWN,
    retryability=RETRYABLE | NON_RETRYABLE
)
```

When retryable, the next TaskAttempt is created only by PyWorkflowKit's `RetryPolicy`.

## Timeout and cancellation

```text
TIMED_OUT
    -> FailureCategory.TIMEOUT

PyTransformKit CANCELLED
    -> ExternalRunRef.status_hint = "cancelled"
    -> known non-retryable EXTERNAL_PROVIDER failure
```

A sibling cancellation is not the same event as a PyWorkflowKit cancellation command.
PyWorkflowKit reserves `TaskAttempt.CANCELLED` for its own
`CANCELLATION_REQUESTED -> CANCELLED` protocol, so LOT-19 does not fabricate a local
cancellation transition from an independently cancelled transformation.

## Unknown outcome and reconciliation

Both sibling uncertainty states:

```text
UNKNOWN_OUTCOME
REQUIRES_RECONCILIATION
```

map to:

```text
FailureEvidence(
    category=UNKNOWN_OUTCOME,
    retryability=RETRYABLE_AFTER_RECONCILIATION,
    uncertainty=REQUIRES_RECONCILIATION
)
```

The workflow becomes `UNKNOWN_OUTCOME` and no blind TaskAttempt N+1 is allocated.

## Credentials

The declaration accepts only an opaque `credential_ref`.

Raw credentials are not part of the public integration contract, and the credential
reference is excluded from durable `ExternalRunRef.metadata`.

## Customer 360 acceptance

LOT-19 completes the first executable cross-framework graph:

```text
ingest_customers ─────┐
                      ├── transform_customer_360 ── publish_mart
ingest_orders ─────────┘
```

Ownership:

```text
ingest_customers        -> PyIngestKit
ingest_orders           -> PyIngestKit
transform_customer_360  -> PyTransformKit
publish_mart            -> PyIngestKit
```

The durable handoff is:

```text
PyIngestKit dataset-version-shaped JSON
        ↓
PyTransformKit portable dependency inputs
        ↓
ResourceReference(scheme, locator, media_type, metadata)
        ↓
PyIngestKit publication task
```

All four tasks retain attempt-scoped external-provider evidence.

## Compatibility

LOT-19 is additive. No PyTransformKit symbol is promoted to the frozen package root, and
the base package remains importable without PyTransformKit installed.

## Contract snapshot

`v2_pytransformkit_integration_snapshot()` freezes:

```text
atomic transformation-plan boundary
no core PyTransformKit dependency
RegisteredWorkload execution path
V2WorkloadBinding integration
strict portable dependency handoff
real ResourceReference field shape
TransformationExecutionId -> ExternalRunRef
PyWorkflowKit workload retry ownership
PyTransformKit provider retry ownership
unknown-outcome reconciliation
credential-reference-only posture
```

## Exit criteria

```text
[ ] PyTransformKitWorkload exists
[ ] planner reports required integration "pytransformkit"
[ ] engine is explicit
[ ] ResourceReference matches scheme/locator/media_type/metadata
[ ] dependency inputs are portable before sibling execution
[ ] success returns resource checkpoint + ExternalRunRef
[ ] transformation_execution_id is persisted as external execution identity
[ ] confirmed failure maps to KNOWN FailureEvidence
[ ] PyWorkflowKit owns workload retry
[ ] PyTransformKit provider retry remains sibling-owned
[ ] TIMED_OUT preserves timeout semantics and sibling CANCELLED remains external evidence
[ ] UNKNOWN_OUTCOME/REQUIRES_RECONCILIATION do not blind-retry
[ ] credential_ref is excluded from ExternalRunRef metadata
[ ] Customer 360 succeeds end-to-end
[ ] package root remains unchanged
[ ] CI is green
[ ] Release Qualification is green
```
