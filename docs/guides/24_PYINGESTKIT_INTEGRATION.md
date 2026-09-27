# 24 — PyIngestKit Integration

## What you will learn

You will integrate one complete PyIngestKit job as one atomic PyWorkflowKit workload
without duplicating the ingestion runtime.

## Fundamental boundary

```text
PyWorkflowKit Task
      ↓
PyIngestKit adapter
      ↓
PyIngestKit Job
      ↓
PyIngestKit Run
```

PyWorkflowKit must not reinterpret PyIngestKit's internal acquire/RAW/parse/validate/profile/
diff/publish lifecycle as its own task graph.

## Retry ownership

The default integration rule is that PyIngestKit owns its internal retry and the surrounding
PyWorkflowKit task does not multiply it.

When PyWorkflowKit explicitly owns retry, the external PyIngestKit wrapper must disable the
foreign retry loop.

## Evidence

A successful integration normalizes into PyWorkflowKit evidence:

```text
TaskResult
    ├── ArtifactReference[]
    └── ExternalRunRef(provider="pyingestkit")
```

The external run reference preserves the PyIngestKit run identity and optional URI.

## Generic future-facing contract

The specialized adapter remains supported, while new foreign runtimes should generally
target the generic `ExternalWorkload` contract described in chapter 20.

## Related example

Canonical integration companion: [`examples/integrations/pyingestkit/atomic_job.py`](../../examples/integrations/pyingestkit/atomic_job.py).

## Related notebook

DX05 target: `17 - PyIngestKit Integration.ipynb`.

## Next chapter

Continue with [25 — Testing Workflows](25_TESTING_WORKFLOWS.md).
