# PyWorkflowKit V2 Migration Evidence Baseline

LOT-00 reserves immutable migration fixtures for the 1.1 → 2.0 line.

## Published persistence history

The following Alembic revisions are historical evidence and must not be rewritten:

```text
0001_runtime_metadata
0002_task_output_checkpoints
0003_retry_eligible_at
```

LOT-10 and LOT-17 must add new revisions on top of this history.

## Legacy evidence classes to preserve

Fixtures added by later lots should cover:

```text
terminal WorkflowRun
non-terminal WorkflowRun
TaskRun with multiple attempts
retry_eligible_at
RuntimeEvent ordering
ArtifactReference
ExternalRunRef
task output checkpoint
legacy failure fields
SQLite database at migration head 0003
PostgreSQL schema at migration head 0003
```

## Migration rule

Legacy evidence may be decoded or projected into V2 read models, but migration must not
invent facts that were never stored.

In particular it must not invent:

```text
definition fingerprint
plan fingerprint
CorrelationContext
TaskAttempt ownership for ambiguous ExternalRunRef rows
successful reconciliation
retryability
```
