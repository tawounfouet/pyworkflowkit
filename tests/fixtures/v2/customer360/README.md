# Customer 360 V2 Fixture Baseline

This directory reserves the canonical cross-framework acceptance scenario used by
LOT-18 → LOT-21.

## Topology

```text
ingest_customers ───┐
                    ├── transform_customer_360
ingest_orders ──────┘
                              │
                              ▼
                         publish_mart
```

## Ownership

- PyWorkflowKit owns dependency ordering, TaskRun/TaskAttempt identities, workload retry and recovery.
- PyIngestKit owns both ingestion workloads and final publication semantics.
- PyTransformKit owns the transformation plan, transformation execution and provider-level retry.

## Durable handoff

Expected portable handoff:

```text
ingest task
    → DatasetVersionReference

transform task
    → ResourceReference(scheme, locator, media_type, metadata)

publish task
    → PyIngestKit-owned publication result/reference
```

No DataFrame or sibling ORM entity is required for recovery.

## Executable status after LOT-19

LOT-19 now provides executable acceptance for:

1. happy-path ingestion → transform → publication;
2. portable JSON handoff and durable task-output checkpoints;
3. sibling-owned ExternalRunRef evidence for ingestion, transformation and publication;
4. confirmed transformation failure and PyWorkflowKit-owned retry;
5. transformation UNKNOWN_OUTCOME with no blind retry;
6. credential-reference exclusion from external-run metadata.

LOT-20 adds cross-framework qualification for:

1. process restart and reconciliation of the same TaskAttempt;
2. transformation and publication UNKNOWN_OUTCOME;
3. provider cancellation discovered during reconciliation;
4. retry-scope amplification controls;
5. correlation/causation propagation;
6. missing optional sibling isolation.

LOT-21 closes the remaining beta/migration qualification line:

1. incompatible sibling integration-contract handling;
2. full lineage traversal from WorkflowRun to sibling execution/data references;
3. V1 migration evidence and compatibility-shim decisions.


## Beta gate after LOT-21

LOT-21 promotes Customer 360 from a cross-framework conformance fixture to the V2 beta
gate.

The gate now includes:

1. complete four-task execution;
2. workflow-level retry on the transformation task;
3. portable output checkpoints;
4. inherited publication UNKNOWN_OUTCOME and SQLite restart/reconciliation from LOT-20;
5. full ExecutionLineage traversal;
6. credential-reference non-disclosure;
7. non-portable dependency fail-closed behavior;
8. execution from installed wheel artifacts on Python 3.11/3.12/3.13;
9. execution from installed sdist on Python 3.13;
10. fail-closed rejection of incompatible PyIngestKit/PyTransformKit integration contracts.

The installed-artifact gate is implemented by:

```text
scripts/qualify_v2_customer360_beta.py
```

and is invoked by Release Qualification from `/tmp`.
