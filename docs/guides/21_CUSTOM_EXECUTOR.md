# 21 — Custom Executor

## What you will learn

You will understand the contract a third-party executor must satisfy and where its
responsibility ends.

## Public contract

Use the ecosystem facade:

```python
from pyworkflowkit.ecosystem import (
    Executor,
    ExecutorCapabilities,
    RunContext,
    TaskDefinition,
    TaskResult,
)
```

Conceptual shape:

```python
class MyExecutor:
    key = "my-executor"

    @property
    def capabilities(self) -> ExecutorCapabilities: ...

    def execute(
        self,
        *,
        task: TaskDefinition,
        handler,
        context: RunContext,
    ) -> TaskResult: ...
```

The implementation should satisfy the runtime-checkable `Executor` protocol.

## Responsibility boundary

A custom executor may decide *how to invoke* the workload. It must not decide:

- whether the task is ready;
- whether a failure should retry;
- whether the workflow should fail;
- how domain state transitions;
- how metadata transactions are committed.

## Capabilities

Declare capabilities truthfully. Parallelism, timeout strength, cancellation strength,
async support, and concurrency limits are runtime contracts, not marketing flags.

## Testing

A custom executor should be tested against the executor contract and, when packaged as a
plugin, the ecosystem conformance checks.

## Related example

Canonical companion: [`examples/20_custom_executor.py`](../../examples/20_custom_executor.py).

## Related notebook

Use [`14 - Executors.ipynb`](<../../notebooks/14 - Executors.ipynb>) to inspect executor
capabilities interactively before implementing a custom executor.

## Next chapter

Continue with [22 — Custom Metadata Store](22_CUSTOM_METADATA_STORE.md).
