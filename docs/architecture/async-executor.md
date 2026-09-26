# M33 — AsyncExecutor

M33 extends the 0.5.x multi-executor line with explicit asyncio workload execution.

## Scope

The implementation follows the executor architecture direction:

```text
asyncio
network I/O
async APIs
Task.cancel()
explicit async boundary
```

M33 does not replace the synchronous Executor port and does not make every handler
implicitly awaitable.

## Explicit async extension

The port layer now exposes a separate async execution contract:

```python
class AsyncExecutor(Protocol):
    async def execute_async(
        self,
        *,
        task: TaskDefinition,
        handler: AsyncTaskHandler,
        context: RunContext,
    ) -> TaskResult: ...
```

The concrete adapter also implements the historical synchronous `execute()` shape as a
compatibility bridge. Native async callers should prefer `execute_async()`.

This follows the architecture rule:

```text
explicit extension
    >
magical sync/async unification
```

## Runtime model

The concrete AsyncExecutor owns one dedicated asyncio event loop running in one daemon
thread.

```text
ConcurrentRunner thread
        │
        │ submit()
        ▼
AsyncExecutor
        │
        │ call_soon_threadsafe
        ▼
dedicated event loop thread
        │
        ├── asyncio.Task A
        ├── asyncio.Task B
        └── asyncio.Task C
        │
        ▼
AttemptCompletion
        │
        ▼
CompletionQueue
        │
        ▼
ConcurrentRunner
```

The event loop executes workloads. It does not own workflow state transitions.

## Handler contract

Tasks assigned to:

```text
executor_key = "async"
```

must resolve to callables accepting either:

```text
()
```

or:

```text
(RunContext)
```

and must return an awaitable.

A synchronous handler used with AsyncExecutor is rejected with `InvalidHandlerError`.

Async handler exceptions are normalized to the existing `TaskExecutionError` contract.

## Capabilities

AsyncExecutor declares:

```text
supports_parallelism = true
supports_async       = true
timeout              = soft
cancellation         = cooperative
max_concurrency      = configured value
```

The default max_concurrency is 100 because the primary use case is I/O-bound async work.

## Concurrency

The same CapacityManager used by ConcurrentRunner remains the coordinator-level source
of dispatch capacity.

AsyncExecutor additionally rejects direct submissions beyond its declared active
capacity so its standalone behavior cannot silently exceed its own capability contract.

No worker process or thread is created per task.

## Cooperative cancellation

AsyncExecutor maps one ExecutionHandle to one physical asyncio.Task.

```text
CancellationController
        ↓
ConcurrentRunner
        ↓
AsyncExecutor.cancel(handle)
        ↓
asyncio.Task.cancel()
        ↓
CancelledError at an await point
        ↓
AttemptCompletion
        ↓
coordinator marks attempt/task CANCELLED
```

This is cooperative cancellation.

It is not equivalent to ProcessExecutor hard termination. A coroutine may run cleanup
logic before finishing and can technically suppress cancellation.

ConcurrentRunner therefore distinguishes:

```text
CancellationCapability.HARD
    → terminate(handle)

CancellationCapability.COOPERATIVE
    → cancel(handle)
```

## Cancellation polling

ThreadExecutor declares no cancellation capability and retains its existing blocking
completion behavior.

ProcessExecutor and AsyncExecutor require the coordinator to periodically re-check the
external CancellationController while work is active.

The polling interval remains an implementation detail of the synchronous coordinator.

## Timeout

AsyncExecutor declares `TimeoutCapability.SOFT`.

A timeout remains:

```text
logical attempt deadline
        ↓
ExecutionTimeoutError
        ↓
TaskAttempt FAILED
        ↓
RetryEngine
```

M33 does not reinterpret `Task.cancel()` as hard timeout.

The physical async task may finish after the logical timeout. Its late completion cannot
overwrite persisted timeout state, and its capacity is released only after physical
completion.

This preserves the invariant introduced by M31/M32:

> one task lineage does not start its retry while the previous physical execution is
> still active.

## Result and context boundary

AsyncExecutor runs in the same process.

Therefore unlike ProcessExecutor:

```text
no pickle boundary
no transport snapshot
no process isolation
```

RunContext remains immutable and is passed directly to the coroutine.

TaskResult normalization uses the existing Python result normalizer.

## Lifecycle

AsyncExecutor owns:

- one event loop;
- one event-loop thread;
- active asyncio.Task objects;
- ExecutionHandle registration;
- completion publication;
- cooperative cancellation;
- shutdown.

`shutdown(wait=True)` waits for active tasks to settle and then stops the loop.

`shutdown(wait=False)` requests cancellation of active tasks and returns while the
daemon loop drains them. The loop stops automatically when it becomes idle.

## Public API

M33 does not expand the package-root API.

Use:

```python
from pyworkflowkit.adapters.executors.asyncio import AsyncExecutor
```

The port extension is available from:

```python
from pyworkflowkit.ports.executor import AsyncExecutor
```

## Acceptance gates

M33 is qualified by:

- native `await execute_async()`;
- synchronous compatibility bridge;
- awaitable-handler validation;
- RunContext propagation;
- TaskResult normalization;
- async exception normalization;
- async fan-out concurrency;
- bounded active capacity;
- ExecutionHandle completion transfer;
- cooperative `Task.cancel()`;
- workflow-level cooperative cancellation;
- soft timeout integration;
- duplicate-attempt protection;
- shutdown lifecycle;
- Python 3.11 / 3.12 / 3.13 CI;
- Ruff;
- strict mypy;
- branch coverage;
- wheel install smoke;
- reference acceptance;
- PostgreSQL regression contract.

## Boundary

M33 does not implement:

- shell or external-program execution — M34 SubprocessExecutor;
- observability plugins — M35;
- security hardening — M36;
- distributed async workers;
- scheduler ownership;
- recovery/resume;
- hard coroutine termination;
- implicit sync-to-thread conversion.
