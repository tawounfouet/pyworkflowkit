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

- PyWorkflowKit owns dependency ordering, TaskRun/TaskAttempt identities, retry and recovery.
- PyIngestKit owns both ingestion workloads and final publication semantics.
- PyTransformKit owns the transformation plan and transformation execution.

## Durable handoff

Expected portable handoff:

```text
ingest task
    → DatasetVersionReference

transform task
    → ResourceReference

publish task
    → PyIngestKit-owned publication result/reference
```

No DataFrame or sibling ORM entity is required for recovery.

## Required qualification variants

Later lots must add executable fixtures for:

1. happy-path ingestion → transform → publication;
2. confirmed sibling failure followed by workflow retry;
3. UNKNOWN_OUTCOME with no blind retry;
4. process restart and reconciliation of the same TaskAttempt;
5. cancellation requested but unconfirmed;
6. portable reference roundtrip;
7. missing optional sibling;
8. incompatible sibling version;
9. credential-reference redaction;
10. lineage traversal from WorkflowRun to sibling execution/data references.
