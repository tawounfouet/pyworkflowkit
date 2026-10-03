# PyWorkflowKit V2 — LOT-19 PyTransformKit Integration

## Status

LOT-19 introduces the canonical V2 anti-corruption boundary between PyWorkflowKit and
PyTransformKit.

The integration is dependency-free:

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
    owns workflow retry/recovery
    owns durable execution evidence

PyTransformKit
    owns transformation-plan semantics
    owns transformation execution
    owns transformation resource semantics
```

One PyWorkflowKit task represents one complete PyTransformKit transformation plan.

PyWorkflowKit does not reproduce transform operators, expressions, schemas, providers or
execution-engine internals.

## Portable workload declaration

LOT-19 adds:

```text
PyTransformKitWorkload
    is-a RegisteredWorkload
```

Its canonical registry key is:

```text
pytransformkit:<plan_ref>
```

and it exposes:

```text
integration_key = "pytransformkit"
```

The existing planner therefore reports PyTransformKit as an explicit sibling
requirement while existing V2 executors continue to resolve the workload through the
standard registered-workload path.

## Input handoff

Transformation inputs come exclusively from upstream
`TaskExecutionContext.dependency_outputs`.

Before calling the sibling wrapper, LOT-19 normalizes every dependency output through
the canonical strict JSON portability rules:

```text
dependency output
      ↓
normalize_json_value
      ↓
plain_json_value
      ↓
PyTransformKitExecutionJob.run(inputs=...)
```

If an upstream output is process-local or otherwise non-portable, the transformation
fails closed before any sibling execution starts.

No pandas DataFrame, Polars DataFrame, ORM entity or arbitrary Python object is required
to recover the workflow.

## ResourceReference anti-corruption DTO

LOT-19 defines:

```text
PyTransformKitResourceReference
```

This is a PyWorkflowKit-owned boundary DTO, not a claim that PyWorkflowKit owns the
sibling's internal resource model.

Its portable representation contains:

```text
kind = pytransformkit.resource_reference
resource_id
uri
version?
metadata
contract_version
```

The V2 runtime persists this data-only representation as the task output checkpoint.

## Normalized transformation result

The sibling wrapper returns:

```text
PyTransformKitExecutionResult
```

with one of:

```text
SUCCEEDED
FAILED
UNKNOWN_OUTCOME
```

Every result has an `external_run_id`, projected into:

```text
ExternalRunRef(
    provider="pytransformkit",
    kind="transformation_execution",
    ...
)
```

## Success mapping

```text
PyTransformKitExecutionResult(SUCCEEDED)
        ↓
PyTransformKitResourceReference
        ↓
portable output checkpoint
        +
ExternalRunRef
```

## Confirmed failure mapping

```text
PyTransformKitExecutionResult(FAILED)
        ↓
FailureEvidence(
    category=EXTERNAL_PROVIDER,
    uncertainty=KNOWN,
    retryability=RETRYABLE | NON_RETRYABLE
)
```

A confirmed retryable transformation failure may be retried by PyWorkflowKit when
PyWorkflowKit is the declared retry owner.

## Unknown outcome mapping

```text
PyTransformKitExecutionResult(UNKNOWN_OUTCOME)
        ↓
FailureEvidence(
    category=UNKNOWN_OUTCOME,
    retryability=RETRYABLE_AFTER_RECONCILIATION,
    uncertainty=REQUIRES_RECONCILIATION
)
        ↓
TaskAttempt.REQUIRES_RECONCILIATION
TaskRun.UNKNOWN_OUTCOME
WorkflowRun.UNKNOWN_OUTCOME
```

No blind second attempt is created.

## Retry ownership

Exactly one runtime owns workload retry.

### PyTransformKit-owned retry

```text
retry_owner = pytransformkit
PyWorkflowKit RetryPolicy.max_attempts = 1
```

Configuring multiple PyWorkflowKit attempts raises
`PyTransformKitRetryOwnershipError`.

### PyWorkflowKit-owned retry

```text
retry_owner = pyworkflowkit
```

The sibling wrapper reports a structured confirmed failure and PyWorkflowKit owns the
next-attempt decision.

## Credentials

The task declaration accepts only an opaque:

```text
credential_ref
```

Raw credentials are not a supported boundary field.

The credential reference is excluded from durable `ExternalRunRef.metadata`.

## Customer 360 executable acceptance

LOT-19 completes the reserved cross-framework fixture:

```text
ingest_customers ─────┐
                      ├── transform_customer_360 ── publish_mart
ingest_orders ─────────┘
```

Ownership is:

```text
ingest_customers        → PyIngestKit
ingest_orders           → PyIngestKit
transform_customer_360  → PyTransformKit
publish_mart            → PyIngestKit
```

The handoffs are all durable JSON-portable values:

```text
PyIngestKit dataset-version-shaped output
        ↓
PyTransformKit portable dependency inputs
        ↓
PyTransformKitResourceReference
        ↓
PyIngestKit publication task
```

The acceptance test also verifies the durable external provider references for all four
tasks.

## Plugin binding

LOT-19 consumes the LOT-16 contract:

```text
PyTransformKitWorkload
        ↓
pytransformkit_v2_workload_binding(...)
        ↓
V2WorkloadBinding
        ↓
registered V2 executor
```

No new executor abstraction is introduced.

## Compatibility

LOT-19 is additive.

No PyTransformKit symbol is promoted to the frozen package root.

The base package remains importable without PyTransformKit installed.

## Contract snapshot

`v2_pytransformkit_integration_snapshot()` freezes:

```text
atomic transformation-plan boundary
no core PyTransformKit dependency
RegisteredWorkload execution path
V2WorkloadBinding integration
portable dependency handoff
portable resource-reference output
ExternalRunRef execution evidence
unknown-outcome reconciliation
credential-reference-only posture
single retry owner
```

## Exit criteria

LOT-19 is complete when:

```text
[ ] PyTransformKitWorkload exists
[ ] workload is portable and registry-backed
[ ] planner reports required integration "pytransformkit"
[ ] PyTransformKitResourceReference is data-only and checkpointable
[ ] dependency inputs are validated for portability before sibling execution
[ ] V2 workload binding exists
[ ] success returns resource reference + ExternalRunRef
[ ] confirmed failure maps to KNOWN FailureEvidence
[ ] retryable confirmed failure can be owned by PyWorkflowKit
[ ] PyTransformKit-owned retry forbids multiple PyWorkflowKit attempts
[ ] UNKNOWN_OUTCOME requires reconciliation and does not blind-retry
[ ] wrapper exceptions fail closed
[ ] credential_ref is not emitted in ExternalRunRef metadata
[ ] Customer 360 cross-framework workflow succeeds end-to-end
[ ] package root remains unchanged
[ ] CI is green
[ ] Release Qualification is green
```
