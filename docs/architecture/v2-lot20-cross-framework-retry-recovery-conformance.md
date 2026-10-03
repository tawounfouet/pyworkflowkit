# PyWorkflowKit V2 — LOT-20 Cross-Framework Retry and Recovery Conformance

## Status

LOT-20 qualifies the reliability boundary formed by:

```text
PyWorkflowKit
    +
PyIngestKit
    +
PyTransformKit
```

No new orchestration engine is introduced. The lot proves that the contracts delivered by
LOT-07 through LOT-19 compose without retry amplification, identity loss, uncertainty
erasure or duplicate sibling execution after restart.

## Ownership model

```text
PyWorkflowKit
    owns TaskRun / TaskAttempt
    owns workload-level retry
    owns workflow recovery and reconciliation
    owns durable ExternalRunRef evidence

PyIngestKit
    may own its ingestion-internal retry scope
    owns ingestion/publication execution semantics

PyTransformKit
    owns engine/provider retry
    owns TransformationExecution
    owns transformation resource semantics
```

Equivalent workload retry scopes must not be stacked implicitly.

## Retry amplification conformance

PyIngestKit retains its explicit retry-owner contract:

```text
retry_owner = pyingestkit
    -> PyWorkflowKit max_attempts must be 1

retry_owner = pyworkflowkit
    -> PyWorkflowKit may allocate TaskAttempt N+1
```

PyTransformKit has a different boundary:

```text
PyWorkflowKit RetryPolicy
    -> creates a new TaskAttempt
    -> creates a new TransformationExecutionId

PyTransformKit provider retry
    -> remains inside one TransformationExecution
```

LOT-20 verifies that provider retry evidence can be carried with each external execution
without multiplying the number of workflow attempts.

## Durable uncertainty

An uncertain sibling result remains attached to the exact TaskAttempt that created it.

```text
TaskAttempt N
    -> ExternalRunRef
    -> UNKNOWN_OUTCOME / REQUIRES_RECONCILIATION
    -> process exits
    -> SQLite reopened
    -> verifier observes provider truth
    -> same TaskAttempt N resolved
```

Reconciliation never creates TaskAttempt N+1.

## Transformation recovery

The conformance scenario executes:

```text
PyIngestKit ingestion
    ->
PyTransformKit transformation
```

The transformation reports UNKNOWN_OUTCOME. The workflow and external reference are
persisted to SQLite. After reopening the store, a PyTransformKit verifier reports
SUCCEEDED.

Expected result:

```text
same TransformationExecution external id
same TaskAttempt
TaskAttempt -> SUCCEEDED
TaskRun     -> SUCCEEDED
WorkflowRun -> SUCCEEDED
no transformation re-execution
```

## Publication uncertainty

The complete Customer 360 graph is exercised:

```text
ingest_customers ─────┐
                      ├── transform_customer_360 ── publish_mart
ingest_orders ─────────┘
```

The publication step reports UNKNOWN_OUTCOME after the transformation output checkpoint
is already durable.

LOT-20 proves that:

- ingestion and transformation are not replayed;
- the portable transformation ResourceReference survives restart;
- the publication ExternalRunRef survives restart;
- provider reconciliation resolves the original publication TaskAttempt;
- the workflow becomes SUCCEEDED when provider truth is conclusive.

## Cancellation truth

Cancellation discovered through reconciliation is provider truth about the ambiguous
external execution.

```text
TaskAttempt REQUIRES_RECONCILIATION
    +
ExternalRunRef(provider=pytransformkit)
    +
verifier -> CANCELLED
        ↓
same TaskAttempt -> CANCELLED
same TaskRun     -> CANCELLED
WorkflowRun      -> CANCELLED
```

This is distinct from the LOT-19 direct adapter rule where a sibling-returned
`CANCELLED` result must not fabricate a local cancellation command transition.

## Correlation and causation

All sibling ExternalRunRef values must preserve the workflow correlation boundary.

The Customer 360 publication-uncertainty scenario freezes:

```text
correlation_id = C-LOT20
causation_id   = request-42
```

across ingestion, transformation and publication evidence.

## Portable handoff

The durable cross-framework handoff remains data-only:

```text
PyIngestKit DatasetVersion-shaped output
    -> JSON checkpoint
    -> PyTransformKit dependency input

PyTransformKit ResourceReference
    -> JSON checkpoint
    -> PyIngestKit publication dependency input
```

No DataFrame, engine handle, ORM instance or arbitrary Python object is required for
restart reconciliation.

## Optional dependency isolation

PyWorkflowKit core and both V2 anti-corruption modules must import successfully while any
attempt to import:

```text
pyingestkit
pytransformkit
```

is actively rejected.

The adapters are therefore boundary contracts, not implicit sibling-package dependencies.

## Executable acceptance

The canonical LOT-20 test module is:

```text
tests/integration/test_v2_lot20_cross_framework_conformance.py
```

It proves:

1. equivalent workload retry scopes are not stacked;
2. provider retry evidence does not create hidden TaskAttempts;
3. transformation UNKNOWN_OUTCOME survives SQLite restart;
4. reconciliation resolves the same transformation TaskAttempt;
5. publication UNKNOWN_OUTCOME survives the complete Customer 360 handoff;
6. publication reconciliation does not replay upstream work;
7. provider CANCELLED truth resolves the same ambiguous attempt;
8. correlation and causation survive every sibling ExternalRunRef;
9. portable task-output checkpoints survive restart;
10. PyWorkflowKit imports without either sibling package.

## Exit criteria

LOT-20 is complete when:

```text
[ ] no equivalent retry scope is stacked implicitly
[ ] retry amplification is explicitly countable
[ ] UNKNOWN_OUTCOME survives both sibling adapters
[ ] publication uncertainty is durable
[ ] cancellation truth is preserved
[ ] SQLite restart preserves ExternalRunRef ownership
[ ] reconciliation resolves the original TaskAttempt
[ ] reconcilable work is not executed twice
[ ] correlation/causation survives sibling boundaries
[ ] cross-framework outputs remain portable
[ ] optional sibling dependencies remain isolated
[ ] Customer 360 conformance tests are green
[ ] CI is green
[ ] Release Qualification is green
```
