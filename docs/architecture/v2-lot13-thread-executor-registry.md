# PyWorkflowKit V2 — LOT-13 ThreadExecutor and Executor Registry

## Status

Implemented on top of LOT-12 execution evidence.

LOT-13 introduces canonical per-task executor routing and the first advanced V2 executor
adapter without changing the WorkflowRuntime into a concurrent DAG scheduler.

## ExecutorRegistry

The canonical qualified surface now includes:

```text
pyworkflowkit.executors.ExecutorRegistry
```

The registry owns explicit:

```text
executor_id → Executor
```

resolution.

Registration is deterministic and duplicate executor identifiers are rejected unless the
same executor instance is registered idempotently.

```python
registry = ExecutorRegistry(
    (
        InlineExecutor(),
        ThreadExecutor(max_workers=4),
    )
)
```

The frozen package root remains unchanged.

## WorkflowRuntime composition

The historical V2 constructor remains valid:

```python
WorkflowRuntime(
    executor=InlineExecutor(),
    metadata=store,
)
```

LOT-13 additionally supports:

```python
WorkflowRuntime(
    executor_registry=registry,
    metadata=store,
)
```

and late explicit registration:

```python
runtime.register_executor(executor)
```

Preflight, execution and cancellation now resolve the executor from the planned
`executor_key` for each task.

## Important non-goal

LOT-13 does **not** make WorkflowRuntime a concurrent DAG scheduler.

The current orchestration loop remains deterministic and sequential:

```text
task A
  ↓
task B
  ↓
task C
```

A ThreadExecutor executes one requested TaskAttempt on a worker thread while the
synchronous runtime waits for the result.

Concurrent fan-out scheduling remains a separate later contract.

## ThreadExecutor

The canonical adapter is:

```text
pyworkflowkit.executors.ThreadExecutor
```

It executes trusted Python workloads in a bounded `ThreadPoolExecutor`.

Supported workload kinds:

```text
python_callable
registered
```

The adapter is same-process and shared-memory by design.

It is not a sandbox.

## Capability contract

The descriptor declares:

```text
executor_id = thread

capabilities
    bounded_thread_pool
    synchronous_bridge
    trusted_python

execution_mode
    worker_thread

supports_execution_timeout = true

cancellation_capability = unsupported

performs_implicit_workload_retry = false
```

The executor never owns retry policy.

## Timeout semantics

Thread timeout is deliberately **soft**.

If the deadline expires before work can continue, the outcome is known:

```text
TIMEOUT
uncertainty = KNOWN
```

If a running thread exceeds the deadline and cannot be cancelled:

```text
TIMEOUT
uncertainty = REQUIRES_RECONCILIATION
retryability = RETRYABLE_AFTER_RECONCILIATION
```

PyWorkflowKit therefore never claims the thread has stopped.

This prevents the dangerous sequence:

```text
thread still running
      +
runtime assumes timeout stopped work
      +
Attempt N+1 starts
      =
duplicate side effect
```

Instead, WorkflowRuntime resolves the uncertain timeout through the existing LOT-07/09
safety rules and returns UNKNOWN_OUTCOME without creating a blind new attempt.

## Cancellation

Active hard cancellation is not claimed.

```text
ThreadExecutor.cancellation_capability
    = UNSUPPORTED
```

Python threads cannot be forcibly terminated safely by the framework.

WorkflowRuntime therefore returns an explicit unsupported cancellation result for active
ThreadExecutor work rather than fabricating cancellation success.

## Registered workloads

ThreadExecutor supports the same explicit registered workload boundary as InlineExecutor:

```python
RegisteredWorkload(
    "jobs.refresh",
    executor_key="thread",
)
```

Bindings remain explicit and process-local:

```python
ThreadExecutor(
    {
        "jobs.refresh": refresh,
    }
)
```

## Multi-executor workflow

A single V2 workflow may now declare different execution strategies:

```text
extract
    executor = inline
        │
        ▼
transform
    executor = thread
```

The TaskRun and TaskAttempt models are unchanged.

Executor selection does not change runtime identity.

## Runtime contract version

The cumulative runtime contract advances to version 4.

It now reports:

```text
durable_outputs = true
basic_events = semantic_projection_from_state_transitions
executor_routing = registry
multi_executor_routing = true
thread_executor = true
```

The first two fields reconcile the machine-readable runtime contract with LOT-12.

## Acceptance invariants

LOT-13 proves:

```text
single-executor constructor remains compatible
registry resolves deterministically
duplicate executor ids are rejected
missing executor fails before WorkflowRun persistence
inline + thread tasks can coexist in one workflow
ThreadExecutor executes on worker thread
registered workload parameters reach the worker
executor never performs implicit retry
soft timeout never claims a running thread stopped
uncertain timeout creates no Attempt N+1
package-root API remains frozen
```

## Next

LOT-14 owns the remaining advanced executor adapters that require stronger execution
boundaries:

```text
ProcessExecutor
AsyncExecutor
SubprocessExecutor
```

Process execution in particular must not be migrated by simply copying the 1.1 adapter.
Its serialization and process-boundary contracts must remain explicit and fail closed.
