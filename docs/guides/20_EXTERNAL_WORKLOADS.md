# 20 — External Workloads

## What you will learn

You will wrap a foreign runtime as one PyWorkflowKit task while preserving retry ownership,
artifacts, and external run identity.

## Public integration contract

The ecosystem SDK exposes:

```python
from pyworkflowkit.ecosystem import (
    ExternalRetryOwner,
    ExternalWorkload,
    ExternalWorkloadAdapter,
    ExternalWorkloadResult,
    external_workload_task,
)
```

## Mental model

```text
PyWorkflowKit Task
      ↓
ExternalWorkloadAdapter
      ↓
foreign runtime / service
      ↓
ExternalWorkloadResult
      ↓
TaskResult
      ├── ArtifactReference[]
      └── ExternalRunRef
```

PyWorkflowKit owns orchestration of the task node. It does not absorb the foreign runtime's
internal lifecycle.

## Retry ownership

Exactly one layer should own automatic retry.

```text
external runtime owns retry
        or
PyWorkflowKit owns retry
```

Independent retry loops at both layers can multiply the effective number of executions.

## Evidence

Successful external execution should preserve the foreign run identity through
`ExternalRunRef`. That reference is evidence and lineage; it is not a copy of the foreign
runtime.

## Common mistakes

- decomposing a foreign runtime's internal lifecycle into fake local tasks;
- enabling retries independently in both systems;
- discarding the foreign run ID;
- returning nonportable metadata without validation.

## Exercises

1. Model one HTTP/remote job as an atomic external workload.
2. Decide which system owns retry.
3. Identify which external identifier should become `ExternalRunRef`.
4. List artifacts that should be propagated to `TaskResult`.

## Related example

DX04 target: `examples/18_external_workload.py`.

## Related notebook

DX05 target: `16 - External Workloads.ipynb`.

## Next chapter

Continue with [21 — Custom Executor](21_CUSTOM_EXECUTOR.md).
