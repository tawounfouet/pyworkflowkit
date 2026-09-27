# PyIngestKit integration example

PyWorkflowKit treats one PyIngestKit job as **one atomic workload**.

Run the normalized adapter example from the repository root:

```bash
python examples/integrations/pyingestkit/atomic_job.py
```

The example does not require the concrete PyIngestKit package. It demonstrates the
anti-corruption contract by implementing the small external job wrapper and returning a
normalized `PyIngestKitRunResult`.

Retry ownership must remain explicit: do not independently enable retries in both
PyWorkflowKit and PyIngestKit.
