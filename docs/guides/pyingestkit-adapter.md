# PyIngestKit adapter

PyWorkflowKit treats a PyIngestKit job as **one atomic workload**.

```text
PyWorkflowKit Task
    ↓
PyIngestKit adapter
    ↓
PyIngestKit Job
    ↓
normalized PyIngestKitRunResult
    ↓
TaskResult + ExternalRunRef
```

The PyWorkflowKit core does **not** import `pyingestkit`. An external wrapper implements
`PyIngestKitJob` and converts the concrete PyIngestKit result into
`PyIngestKitRunResult`.

## Retry ownership

Exactly one runtime owns retries.

### PyIngestKit owns retry

This is the default. The PyWorkflowKit task must use `RetryPolicy(max_attempts=1)`.
`pyingestkit_task()` enforces this rule.

### PyWorkflowKit owns retry

Set `retry_owner=PyIngestKitRetryOwner.PYWORKFLOWKIT` and configure the
PyWorkflowKit `RetryPolicy`. The external PyIngestKit wrapper is then responsible
for disabling internal PyIngestKit retries.

Never enable retries independently in both layers. Otherwise the effective number
of executions multiplies across the two runtimes.

## Evidence

A successful external execution becomes an `ExternalRunRef` with:

- `provider="pyingestkit"`;
- the external PyIngestKit run identifier;
- an optional URI;
- adapter metadata such as the job reference and retry owner.

Artifacts returned by the normalized boundary result are propagated unchanged
into the PyWorkflowKit `TaskResult`.

## Error translation

Exceptions raised by the external wrapper and failed normalized run results are
translated into `PyIngestKitAdapterError`. PyWorkflowKit's normal executor layer
then records the failure through its existing task-attempt, retry, event, metadata,
and manifest mechanisms.
