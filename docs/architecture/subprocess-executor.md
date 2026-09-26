# M34 — SubprocessExecutor

M34 extends the 0.5.x executor family with explicit external-program execution.

## Scope

The source architecture defines this executor for:

```text
CLI command
shell-free argv
external program
stdout
stderr
returncode
```

The implementation preserves that boundary directly.

## Workload contract

A task assigned to:

```text
executor_key = "subprocess"
```

resolves a small Python command factory. The factory accepts either:

```text
()
```

or:

```text
(RunContext)
```

and must return:

```python
SubprocessCommand(
    argv=(...),
)
```

The Python factory is declarative. The external program remains the actual workload.

## Shell boundary

SubprocessExecutor always launches with:

```text
shell = false
```

There is no shell-string execution mode in M34.

```text
SubprocessCommand.argv
        ↓
Popen(argv, shell=False)
        ↓
operating-system process creation
```

Arguments such as:

```text
;
&&
$()
|
>
```

remain argv content and are not interpreted as shell operators.

## Command value

SubprocessCommand carries:

```text
argv
cwd
env
stdin
encoding
```

Validation rejects:

- empty argv;
- blank executable names;
- NUL characters in argv or cwd;
- invalid environment keys and values;
- blank encodings.

The environment is defensively copied and exposed read-only.

## Result value

Successful execution produces:

```python
SubprocessResult(
    argv=...,
    returncode=0,
    stdout=...,
    stderr=...,
)
```

wrapped in TaskResult.

This gives external workloads a natural capture boundary without redirecting process-wide
Python stdout/stderr.

## Non-zero exit

A non-zero process return code becomes:

```text
SubprocessExecutionError
error_category = subprocess_exit
```

The error retains:

```text
argv
returncode
stdout
stderr
```

This preserves process evidence while routing the failure through the ordinary
TaskExecutionError / RetryEngine contract.

## Spawn failure

Failures before a child process exists, such as an unknown executable, are normalized as:

```text
TaskExecutionError
error_category = subprocess_spawn
```

Command-factory Python errors use:

```text
error_category = subprocess_command
```

## Concurrency

SubprocessExecutor owns a bounded set of directly launched external child processes.

```text
max_workers = N
        ↓
at most N active external subprocesses
```

ConcurrentRunner still owns global/per-executor CapacityManager accounting.

The adapter also enforces its declared capacity for direct standalone submissions.

## Completion transfer

```text
external child process
        ↓
watcher
        ↓
stdout / stderr / returncode
        ↓
AttemptCompletion
        ↓
CompletionQueue
        ↓
ConcurrentRunner
```

The watcher owns process reaping. Runtime state transitions remain coordinator-owned.

## Capabilities

SubprocessExecutor declares:

```text
supports_parallelism = true
supports_async       = false
timeout              = hard
cancellation         = hard
max_concurrency      = configured value
```

Hard semantics apply to the directly owned child process.

## Hard timeout

For TimeoutMode.HARD:

```text
deadline
    ↓
ConcurrentRunner
    ↓
terminate(handle)
    ↓
process.terminate()
    ↓ grace period
process.kill() if required
    ↓
ExecutionTimeoutError
    ↓
RetryEngine
```

The runtime does not introduce a new timeout lifecycle status.

## Hard cancellation

Workflow cancellation reuses the same generic hard-termination path already introduced
for ProcessExecutor:

```text
CancellationController
        ↓
ConcurrentRunner
        ↓
terminate(handle)
        ↓
external process exits
        ↓
completion drained
        ↓
TaskAttempt / TaskRun CANCELLED
```

## Direct execute()

The synchronous execute() convenience path launches the external command and waits for
its result.

Workflow timeout policy remains coordinator-owned. The full timeout/cancellation contract
is therefore exercised through ConcurrentRunner + submit()/ExecutionHandle.

## Security boundary

M34 deliberately implements only the minimal safe execution primitive:

```text
explicit argv
shell=False
captured output
direct-child termination
```

The following remain M36 concerns:

- executable allowlists;
- path restrictions;
- environment allow/deny policies;
- output-size quotas;
- stdin quotas;
- process-tree containment;
- resource limits;
- sandboxing;
- privilege reduction;
- secret handling policy.

M34 does not pretend these controls already exist.

## Public API

M34 does not expand the package root.

Use:

```python
from pyworkflowkit.adapters.executors.subprocess import (
    SubprocessCommand,
    SubprocessExecutor,
    SubprocessResult,
)
```

## Acceptance gates

M34 is qualified by:

- shell-free literal argv behavior;
- stdout capture;
- stderr capture;
- return-code capture;
- RunContext-aware command factories;
- stdin support;
- cwd support;
- explicit environment support;
- spawn failure normalization;
- non-zero exit normalization;
- ExecutionHandle completion transfer;
- bounded capacity;
- duplicate-attempt protection;
- per-handle hard termination;
- workflow hard timeout;
- workflow hard cancellation;
- process cleanup/reaping;
- Python 3.11 / 3.12 / 3.13 CI;
- Ruff;
- strict mypy;
- branch coverage;
- reference acceptance;
- wheel install smoke;
- PostgreSQL regression contract.

## Boundary

M34 does not implement:

- shell execution;
- remote execution;
- container execution;
- process-tree sandboxing;
- observability plugins — M35;
- security hardening — M36;
- recovery/resume — 0.6.
