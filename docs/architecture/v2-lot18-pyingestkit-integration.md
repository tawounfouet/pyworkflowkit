# PyWorkflowKit V2 — LOT-18 PyIngestKit Integration

## Status

LOT-18 qualifies the canonical V2 integration boundary between PyWorkflowKit and
PyIngestKit while preserving the existing 1.1 adapter.

The integration remains intentionally dependency-free:

```text
PyWorkflowKit
    does not import
PyIngestKit
```

A concrete sibling package integrates by implementing a very small anti-corruption
protocol and registering one explicit V2 workload binding.

## Atomic workload boundary

The ownership rule is unchanged:

```text
PyWorkflowKit Task
        ↓
one atomic PyIngestKit job
        ↓
PyIngestKit owns its internal ingestion lifecycle
```

PyWorkflowKit does not expand the sibling framework's acquire / RAW / parse / validate /
profile / diff / publish phases into its own DAG.

## V2 workload descriptor

LOT-18 adds:

```text
PyIngestKitWorkload
    is-a RegisteredWorkload
```

This is deliberate. The descriptor therefore works with the existing V2 executor
registry/binding path and does not require a new executor type.

Its canonical registry key is:

```text
pyingestkit:<job_ref>
```

The descriptor also exposes:

```text
integration_key = "pyingestkit"
```

so `WorkflowPlanner` records the sibling requirement explicitly.

## Portable parameters

The descriptor stores only string parameters.

Reserved integration parameters include:

```text
pyingestkit.job_ref
pyingestkit.retry_owner
pyingestkit.credential_ref
```

A credential is never embedded as raw secret material by the helper API.

Only an opaque `credential_ref` may cross the authoring boundary.

The credential reference is not copied into durable `ExternalRunRef.metadata`.

## Retry ownership

Exactly one framework owns workload-level retry.

### PyIngestKit-owned retry

```text
retry_owner = pyingestkit
PyWorkflowKit RetryPolicy.max_attempts = 1
```

Any attempt to configure multiple PyWorkflowKit attempts fails closed.

### PyWorkflowKit-owned retry

```text
retry_owner = pyworkflowkit
PyIngestKit wrapper must not run its own retry loop
```

The wrapper returns structured failure evidence and PyWorkflowKit's V2
`RetryEvaluator` owns the next-attempt decision.

## Normalized sibling result

The V2 wrapper returns:

```text
PyIngestKitExecutionResult
```

with one of three statuses:

```text
SUCCEEDED
FAILED
UNKNOWN_OUTCOME
```

Every normalized result carries an `external_run_id`.

That identity is projected into the canonical V2 `ExternalRunRef` contract.

## Success mapping

```text
PyIngestKitExecutionResult(SUCCEEDED)
        ↓
TaskExecutionResult(
    output=...,
    external_runs=(ExternalRunRef(...),)
)
```

The runtime then owns portable output checkpointing.

## Confirmed failure mapping

```text
PyIngestKitExecutionResult(FAILED)
        ↓
FailureEvidence(
    category=EXTERNAL_PROVIDER,
    uncertainty=KNOWN,
    retryability=RETRYABLE | NON_RETRYABLE
)
```

A confirmed provider failure may participate in normal PyWorkflowKit retry evaluation.

## Unknown outcome mapping

An uncertain sibling outcome must never be converted into an ordinary retryable failure.

```text
PyIngestKitExecutionResult(UNKNOWN_OUTCOME)
        ↓
FailureEvidence(
    category=UNKNOWN_OUTCOME,
    retryability=RETRYABLE_AFTER_RECONCILIATION,
    uncertainty=REQUIRES_RECONCILIATION
)
        ↓
WorkflowRuntime
        ↓
TaskAttempt.REQUIRES_RECONCILIATION
TaskRun.UNKNOWN_OUTCOME
WorkflowRun.UNKNOWN_OUTCOME
```

No blind second `TaskAttempt` is created.

## Wrapper exceptions

If the anti-corruption wrapper raises before producing normalized sibling evidence,
PyWorkflowKit cannot safely infer provider state.

LOT-18 therefore maps wrapper exceptions to a known, non-retryable contract failure:

```text
category = CONTRACT_VIOLATION
retryability = NON_RETRYABLE
```

This avoids accidental duplicate external effects.

## Plugin/binding integration

LOT-18 consumes the LOT-16 binding contract directly:

```text
PyIngestKitWorkload
        ↓
pyingestkit_v2_workload_binding(...)
        ↓
V2WorkloadBinding(
    registry_key="pyingestkit:<job_ref>",
    handler=PyIngestKitWorkloadHandler(...)
)
        ↓
InlineExecutor / ThreadExecutor / ProcessExecutor binding registry
```

The default helper selects `inline`, while callers may choose another registered
executor if the external wrapper is compatible with that execution boundary.

## Planning

A workflow containing PyIngestKit descriptors compiles with:

```text
workload_kind = registered
required_integrations = ("pyingestkit",)
```

This preserves compatibility with the existing executor family while making sibling
requirements visible to planning and diagnostics.

## Customer 360 fixture

LOT-18 establishes the first executable part of the reserved cross-framework fixture:

```text
ingest_customers ───┐
                    ├── transform_customer_360   ← LOT-19
ingest_orders ──────┘
```

The two ingestion nodes are portable, atomic PyIngestKit workloads.

LOT-19 owns the PyTransformKit node and the first complete cross-framework graph.

## Compatibility

The 1.1 API remains available:

```text
PyIngestKitJob
PyIngestKitRunResult
PyIngestKitTaskAdapter
pyingestkit_task(...)
```

LOT-18 adds rather than rebinds:

```text
PyIngestKitExecutionJob
PyIngestKitExecutionResult
PyIngestKitExecutionStatus
PyIngestKitWorkload
PyIngestKitWorkloadHandler
pyingestkit_v2_task(...)
pyingestkit_v2_workload_binding(...)
```

No V2 PyIngestKit symbol is promoted to the frozen package root.

## Contract snapshot

`v2_pyingestkit_integration_snapshot()` freezes:

```text
atomic sibling-job boundary
no PyIngestKit core dependency
RegisteredWorkload execution path
V2WorkloadBinding integration
TaskExecutionResult success contract
FailureEvidence failure contract
ExternalRunRef evidence contract
reconciliation-required unknown outcomes
credential-reference-only posture
no implicit retry multiplication
```

## Exit criteria

LOT-18 is complete when:

```text
[ ] V2 PyIngestKit workload descriptor exists
[ ] descriptor is portable and registry-backed
[ ] planner reports required integration "pyingestkit"
[ ] V2 workload binding exists
[ ] success produces output + ExternalRunRef
[ ] confirmed failure produces KNOWN FailureEvidence
[ ] retryable confirmed failure can be retried by PyWorkflowKit
[ ] PyIngestKit-owned retry forbids multiple PyWorkflowKit attempts
[ ] UNKNOWN_OUTCOME requires reconciliation and does not blind-retry
[ ] wrapper exceptions fail closed
[ ] credential_ref is not emitted in ExternalRunRef metadata
[ ] 1.1 adapter remains unchanged
[ ] package root remains unchanged
[ ] CI is green
[ ] Release Qualification is green
```
