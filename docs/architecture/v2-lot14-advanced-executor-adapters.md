# PyWorkflowKit V2 — LOT-14 Advanced Executor Adapters

## Status

LOT-14 completes the first canonical V2 advanced executor family:

```text
ProcessExecutor
AsyncExecutor
SubprocessExecutor
```

These adapters build on LOT-13 ExecutorRegistry and per-task executor routing.

The V2 WorkflowRuntime remains a deterministic synchronous orchestrator. LOT-14 does not
turn it into a concurrent DAG scheduler.

## Design rule

Executors own physical workload execution.

They do not own:

```text
workflow scheduling
state-machine authority
retry policy
metadata persistence
reconciliation policy
```

Those responsibilities remain in WorkflowRuntime and its existing V2 services.

## ProcessExecutor

Canonical surface:

```text
pyworkflowkit.executors.ProcessExecutor
```

The adapter executes trusted Python handlers in dedicated child processes.

### Physical boundary

```text
TaskExecutionRequest
        │
        ├── handler
        └── TaskExecutionContext snapshot
                │
                ▼
          pickle preflight
                │
        ┌───────┴────────┐
        │                │
      fail            child process
     closed                │
                           ▼
                 TaskExecutionResult
                           │
                           ▼
                     pickle result
                           │
                  ┌────────┴────────┐
                  │                 │
                parent      nonportable result
                                  │
                                  ▼
                         CONTRACT_VIOLATION
```

The process adapter never silently drops or stringifies non-picklable execution data.

### Capabilities

```text
executor_id = process
execution_mode = child_process
supports_execution_timeout = true
cancellation_capability = confirmed
implicit_retry = false
```

Portability constraints are explicit:

```text
handler_must_be_picklable
inputs_must_be_picklable
output_must_be_picklable
trusted_python_not_security_sandbox
```

Process isolation is not presented as a sandbox for untrusted Python.

### Timeout and cancellation

A process deadline is hard:

```text
deadline exceeded
      │
      ▼
terminate()
      │
kill() if required
      │
      ▼
TIMEOUT
uncertainty = KNOWN
```

Cancellation uses the same physical hard-stop capability and therefore returns
`CancellationStatus.CONFIRMED` only after the child process termination request has been
applied.

## AsyncExecutor

Canonical surface:

```text
pyworkflowkit.executors.AsyncExecutor
```

AsyncExecutor owns one dedicated asyncio event loop running in one daemon thread.

```text
WorkflowRuntime
      │
      │ execute()
      ▼
AsyncExecutor
      │
      ▼
dedicated event loop
      │
      └── asyncio.Task
```

It exposes two entry points:

```python
executor.execute(request)
await executor.execute_async(request)
```

The synchronous method is the bridge used by WorkflowRuntime.
The asynchronous method avoids blocking an async caller loop.

### Handler contract

The resolved handler must return an awaitable.

A synchronous value is a structured contract failure:

```text
PWK-ASYNC-NON-AWAITABLE
category = CONTRACT_VIOLATION
```

### Cancellation

Async cancellation is explicitly cooperative.

```text
cancel()
   │
   ▼
asyncio.Task.cancel()
   │
   ▼
CancellationStatus.REQUESTED
```

The adapter never returns CONFIRMED merely because `Task.cancel()` was called.

A coroutine may still:

```text
run cleanup
finish normally
suppress cancellation
```

The physical task remains tracked until it actually completes.

### Timeout

Async timeout is soft.

If the coroutine is already running when the deadline expires:

```text
TIMEOUT
uncertainty = REQUIRES_RECONCILIATION
retryability = RETRYABLE_AFTER_RECONCILIATION
```

That preserves the no-blind-retry invariant from LOT-07/09.

## SubprocessExecutor

Canonical surface:

```text
pyworkflowkit.executors.SubprocessExecutor
pyworkflowkit.executors.SubprocessCommand
pyworkflowkit.executors.SubprocessResult
pyworkflowkit.executors.SubprocessSecurityPolicy
```

### Portable command workload

LOT-14 promotes SubprocessCommand from a legacy handler result into a portable V2 workload
descriptor.

```python
TaskDefinition(
    key="external",
    workload=SubprocessCommand(
        argv=("/usr/bin/python", "-c", "print('hello')"),
    ),
)
```

The planner resolves:

```text
workload_kind = subprocess
executor_key = subprocess
portable = true
```

No handler factory is required for the canonical path.

Registered or callable command factories remain supported for compatibility with the
general executor boundary.

### Shell boundary

Execution is always:

```text
Popen(argv, shell=False)
```

There is no shell-string parsing.

Arguments such as:

```text
; rm -rf /
$(...)
&& ...
```

remain literal argv values.

### Security policy

SubprocessSecurityPolicy can constrain:

```text
allowed executables
allowed working-directory roots
allowed environment keys
environment inheritance
stdin size
stdout size
stderr size
```

The policy reduces command-surface exposure but is not an operating-system sandbox.

### Result contract

A successful command returns:

```text
SubprocessResult
├── argv
├── returncode
├── stdout
└── stderr
```

A non-zero exit becomes structured FailureEvidence rather than an exception escaping the
executor boundary.

### Hard timeout and cancellation

A subprocess is physically terminable.

Therefore deadline expiry and active cancellation are known physical outcomes after
termination:

```text
timeout      → TIMEOUT / KNOWN
cancellation → CONFIRMED
```

## Executor contract v4

The cumulative executor contract advances to version 4 and records:

```text
executor_registry = true
thread_executor = true
process_executor = true
async_executor = true
subprocess_executor = true

process_serialization_boundary = pickle_fail_closed
async_cancellation = cooperative_requested
subprocess_shell = false
```

## Multi-executor runtime

LOT-14 qualifies one DAG routed through all advanced boundaries:

```text
ProcessExecutor
      │
      ▼
AsyncExecutor
      │
      ▼
SubprocessExecutor
```

The routing decision comes exclusively from each TaskPlanEntry.executor_requirement.

Runtime identity remains unchanged:

```text
WorkflowRun
   └── TaskRun
        └── TaskAttempt
```

## Acceptance invariants

LOT-14 proves:

```text
ProcessExecutor runs in a different PID
unpicklable process inputs fail before spawn
unpicklable process outputs become structured failures
process timeout is known after hard termination
process cancellation is confirmed after hard termination

AsyncExecutor requires awaitables
execute_async() is available
async timeout remains uncertain
async cancellation is REQUESTED, never falsely confirmed

SubprocessCommand is portable
subprocess routing is planner-native
shell=False is fixed
non-zero exit is structured evidence
security policy fails closed
captured-output limits are enforced
subprocess timeout is known after termination

mixed process → async → subprocess workflow succeeds
frozen 1.1 package root remains unchanged
```

## Boundary

LOT-14 does not implement:

```text
parallel DAG scheduling
distributed workers
remote execution protocol
container execution
Kubernetes execution
queue/broker execution
executor plugin discovery changes
```

Those remain later roadmap concerns.
