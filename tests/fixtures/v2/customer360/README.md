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

The remaining cross-framework qualification line still owns:

1. process restart and reconciliation of the same TaskAttempt;
2. cancellation requested but unconfirmed;
3. missing optional sibling;
4. incompatible sibling version;
5. full lineage traversal from WorkflowRun to sibling execution/data references.
