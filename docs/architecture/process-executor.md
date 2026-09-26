# M32 — ProcessExecutor

M32 opens the PyWorkflowKit 0.5.x multi-executor hardening line.

## Scope

The implementation follows the roadmap scope exactly:

```text
process pool
serialization constraints
error transfer
cleanup
stronger termination
```

## Execution boundary

`ProcessExecutor` executes trusted Python handlers outside the coordinator process.

```text
ConcurrentRunner
      │
      │ submit
      ▼
ProcessExecutor
      │
      ├── Task transport snapshot
      ├── RunContext transport snapshot
      ├── picklable handler
      │
      ▼
isolated child process
      │
      ├── invoke_python_handler()
      ├── TaskResult snapshot
      └── error snapshot
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

The child process never mutates `WorkflowRun`, `TaskRun`, `TaskAttempt`, metadata
stores, or runtime events. The coordinator remains the only runtime-state authority.

## Why explicit transport snapshots

The domain intentionally uses immutable wrappers such as `MappingProxyType` in
`RunContext`, `TaskResult`, artifacts, and external references.

M32 does not make those domain objects process-aware. Instead it projects them into
plain transport values before crossing the process boundary and reconstructs the domain
representation on the receiving side.

This preserves the existing architecture:

```text
domain model
    !=
process transport representation
```

Handlers, workflow parameters, dependency outputs, task outputs, metadata values, and
other user-provided payloads still need to be serializable.

A transport failure is surfaced as `ExecutorSerializationError`.

## Process capacity model

PyWorkflowKit supports Python 3.11 through 3.13. Across those versions,
`concurrent.futures.ProcessPoolExecutor` does not provide a portable public API for
terminating one specific running future while keeping unrelated work alive.

M32 therefore uses a bounded set of active child processes:

```text
max_workers = N
      ↓
at most N active child processes
      ↓
one ExecutionHandle owns one process
```

This behaves as process-pool capacity from the runtime perspective while retaining
per-handle process ownership for hard termination.

It deliberately does not introduce a distributed worker pool or persistent worker
platform.

## Capabilities

`ProcessExecutor(max_workers=N)` declares:

```text
supports_parallelism = true
timeout              = hard
cancellation         = hard
max_concurrency      = N
```

A HARD capability can satisfy tasks requesting NONE, SOFT, or HARD timeout semantics.

## Hard timeout

For `TimeoutMode.HARD`:

```text
deadline reached
      ↓
terminate(handle)
      ↓
physical child process stops
      ↓
ExecutionTimeoutError
      ↓
existing RetryEngine
```

The domain/evidence contract is unchanged:

- no `TIMED_OUT` status;
- the attempt becomes `FAILED`;
- `error_category = "timeout"`;
- retry continues through the existing retry policy.

A retry is not dispatched until the prior physical execution has been cleaned up.

For `TimeoutMode.SOFT`, the existing logical timeout behavior remains available even
though ProcessExecutor is capable of stronger termination.

## Hard cancellation

When `CancellationController` is requested while ProcessExecutor work is active,
ConcurrentRunner periodically observes the request, terminates still-running handles,
normalizes those active attempts/tasks to `CANCELLED`, drains completion evidence, and
then finalizes the workflow as `CANCELLED`.

If a process completed before termination could be applied, its real terminal completion
is preserved instead.

The existing runtime event taxonomy remains unchanged in M32.

## Error transfer

Ordinary handler exceptions are translated in the child into a transport envelope and
reconstructed in the coordinator as `TaskExecutionError`, preserving:

```text
error_type
error_message
error_category
```

Failures outside the handler contract become `ExecutorWorkerError`.

Result serialization failures become `ExecutorSerializationError`.

## Cleanup

The executor owns:

- child process lifecycle;
- pipe lifecycle;
- watcher lifecycle;
- active handle registration;
- hard termination;
- shutdown.

`shutdown(wait=True)` drains active children naturally.

`shutdown(wait=False)` terminates active child processes before joining watcher
threads.

No process may own workflow persistence or state transitions.

## Public API

M32 does not expand the package-root API.

Use:

```python
from pyworkflowkit.adapters.executors.process import ProcessExecutor
```

The stable 0.4 public root remains unchanged.

## Acceptance gates

M32 is qualified by:

- separate-process PID proof;
- RunContext transport reconstruction;
- TaskResult transport reconstruction;
- handler serialization rejection before launch;
- result serialization failure transfer;
- ordinary handler exception transfer;
- duplicate-attempt protection;
- hard per-handle termination;
- shutdown lifecycle;
- ConcurrentRunner reference success;
- hard timeout reference failure;
- Python 3.11 / 3.12 / 3.13 CI;
- Ruff;
- strict mypy;
- branch coverage;
- package wheel smoke;
- existing persistence/reference suites.

## Boundary

M32 does not implement:

- `AsyncExecutor` — M33;
- `SubprocessExecutor` — M34;
- observability plugins — M35;
- security hardening — M36;
- recovery/resume — 0.6;
- distributed workers;
- scheduler ownership;
- control-plane behavior.
