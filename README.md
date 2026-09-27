# PyWorkflowKit

**Reliable workflows without running a workflow platform.**

PyWorkflowKit is an embedded Python workflow runtime for defining, validating, planning,
executing, persisting, inspecting, and evidencing generic dependency graphs of trusted
Python workloads without requiring a scheduler, server, worker cluster, or orchestration
platform.

> **Status:** stable release `0.6.0`.
> The 0.6 line adds crash-recovery assessment, reconciliation, same-run resume, and
> durable non-blocking retry coordination.

## What 0.6 provides

The `0.5.x` line keeps the complete local developer framework and concurrency foundation
from 0.4, then adds hardened execution and integration:

- immutable `WorkflowDefinition` and `TaskDefinition` domain values;
- deterministic DAG validation and topological planning;
- explicit workflow/task/attempt state machines;
- sequential trusted-Python execution through `LocalExecutor`;
- retry, fail-fast, skip propagation, runtime events, manifests, and lineage;
- `MemoryMetadataStore`, durable SQLite, and optional PostgreSQL persistence;
- SQLAlchemy persistence mappings and Alembic migrations;
- validated runtime configuration from defaults, environment variables, TOML, and
  explicit overrides;
- small public `WorkflowRuntime` facade;
- lazy `@task` and `@workflow` declarative APIs;
- CLI commands for validation, planning, execution, inspection, events, manifests,
  plugin discovery, diagnostics, and version reporting;
- structured diagnostic logging with secret redaction;
- typed plugin registries and opt-in `importlib.metadata` entry-point discovery;
- optional PyIngestKit anti-corruption adapter with explicit retry ownership;
- explicit executor capabilities for parallelism, timeout, cancellation, and concurrency;
- thread-safe global and per-executor capacity accounting;
- `ThreadExecutor` backed by `ThreadPoolExecutor`;
- coordinator-owned concurrent fan-out/fan-in execution through `ConcurrentRunner`;
- graceful workflow cancellation that stops new dispatch and drains already-running work;
- explicit `NONE` / `SOFT` / `HARD` timeout semantics with capability validation;
- timeout failures normalized through the existing retry engine;
- isolated Python execution through `ProcessExecutor`;
- native awaitable workloads through `AsyncExecutor`;
- shell-free external program execution through `SubprocessExecutor`;
- committed-event observability sinks with failure isolation;
- subprocess executable/cwd/environment/I/O guardrails;
- observability payload and sink-error redaction;
- blocking Bandit, pip-audit, and detect-secrets CI security gates.
- read-only stale-run recovery assessment over durable runtime evidence;
- provider-specific reconciliation of ambiguous external executions;
- same-`WorkflowRun` resume with durable portable dependency-output checkpoints;
- durable `retry_eligible_at` evidence and non-blocking concurrent retry backoff.

`WorkflowRuntime` remains the small sequential/local facade. The concurrent runtime is
an advanced API composed explicitly from `ConcurrentRunner` and `ThreadExecutor`.

## Installation

PyWorkflowKit requires Python 3.11 or newer.

```bash
python -m pip install pyworkflowkit
```

For local development:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

PostgreSQL support is optional:

```bash
python -m pip install "pyworkflowkit[postgres]"
```

## Public API example

```python
from pyworkflowkit import TaskHandle, WorkflowRuntime, task, workflow


@task
def fetch() -> dict[str, int]:
    return {"rows": 10}


@task(depends_on=(fetch,))
def publish() -> str:
    return "published"


@workflow(id="demo.etl", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (fetch, publish)


runtime = WorkflowRuntime()
for handle in demo.task_handles():
    runtime.register(handle.handler_ref, handle.handler)

definition = demo.build()
run = runtime.run(definition)
manifest = runtime.manifest(definition, run.run_id)

print(run.status)
print(manifest.run_id)
```

Decoration and import are lazy: defining a task or workflow does not execute a workload.

## Concurrent execution in 0.4

The concurrent runtime is explicit rather than hidden behind the default local facade:

```python
from pyworkflowkit import TaskDefinition, TaskId, TimeoutMode, WorkflowDefinition, WorkflowId
from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry

handlers = HandlerRegistry()
handlers.register("handlers:a", lambda: "a")
handlers.register("handlers:b", lambda: "b")

workflow = WorkflowDefinition(
    workflow_id=WorkflowId("demo.concurrent"),
    version="1",
    tasks=(
        TaskDefinition(
            task_id=TaskId("a"),
            handler_ref="handlers:a",
            executor_key="thread",
            timeout_seconds=5.0,
            timeout_mode=TimeoutMode.SOFT,
        ),
        TaskDefinition(
            task_id=TaskId("b"),
            handler_ref="handlers:b",
            executor_key="thread",
        ),
    ),
)

executor = ThreadExecutor(max_workers=2)
runner = ConcurrentRunner(
    metadata_store=MemoryMetadataStore(),
    handler_registry=handlers,
    executor=executor,
    clock=SystemClock(),
    id_factory=UuidRuntimeIdFactory(),
    sleeper=SystemSleeper(),
    global_limit=2,
)

try:
    run = runner.run(workflow)
finally:
    executor.shutdown(wait=True)
```

Cancellation uses a thread-safe controller passed to the coordinator:

```python
from pyworkflowkit.application.cancellation import CancellationController

cancellation = CancellationController()
cancellation.request(reason="user_requested")
run = runner.run(workflow, cancellation=cancellation)
```

For `ThreadExecutor`, timeout support is intentionally **SOFT**: the logical attempt can
fail on deadline while the Python thread finishes later. Hard thread termination is not
simulated, and `HARD` timeout requests are rejected by capability validation.

## Process execution in 0.5

M32 adds an advanced process-isolated executor:

```python
from pyworkflowkit.adapters.executors.process import ProcessExecutor

executor = ProcessExecutor(max_workers=2)
```

`ProcessExecutor` preserves the same coordinator contract used by `ThreadExecutor`:

```text
worker execution
      ↓
AttemptCompletion
      ↓
CompletionQueue
      ↓
ConcurrentRunner
      ↓
runtime state transitions
```

The process boundary is explicit. `RunContext` and `TaskResult` are projected through
process-safe transport snapshots instead of relying on accidental pickling of domain
objects. Registered handlers and transported values must themselves be serializable.

The executor declares:

```text
parallelism  = true
timeout      = hard
cancellation = hard
```

For Python 3.11-3.13, each active execution handle owns an isolated child process inside
a bounded active-process set. This intentionally favors reliable per-handle termination
over pretending that the standard `ProcessPoolExecutor` can terminate an individual
running future on every supported Python version.

A `HARD` timeout terminates the physical process before the existing timeout failure
is normalized through `ExecutionTimeoutError` and the ordinary retry path. A `SOFT`
timeout keeps the existing logical-timeout semantics.

`ProcessExecutor` remains an advanced module import and is not added to the package-root
API.


## Async execution in 0.5

M33 adds an advanced asyncio executor for I/O-bound and natively asynchronous workloads:

```python
from pyworkflowkit.adapters.executors.asyncio import AsyncExecutor

executor = AsyncExecutor(max_concurrency=100)
```

Handlers assigned to `executor_key="async"` must return an awaitable. Native callers can
use the explicit async extension directly:

```python
result = await executor.execute_async(
    task=task_definition,
    handler=async_handler,
    context=run_context,
)
```

`ConcurrentRunner` continues to use the existing submission/completion boundary:

```text
async handler
    ↓
asyncio.Task
    ↓
ExecutionHandle
    ↓
AttemptCompletion
    ↓
CompletionQueue
    ↓
ConcurrentRunner
```

The executor declares:

```text
parallelism   = true
async         = true
timeout       = soft
cancellation  = cooperative
```

Cancellation uses `asyncio.Task.cancel()`. This is intentionally **cooperative**, not
hard termination: a coroutine receives cancellation at an await point and may perform
cleanup or, if written poorly, suppress cancellation.

Timeout remains `SOFT` for the same reason. A logical timeout is recorded through the
existing `ExecutionTimeoutError` contract, while physical coroutine completion is still
drained before the same task lineage can be retried.

`AsyncExecutor` remains an advanced module import and is not added to the package-root
API.

## External subprocess execution in 0.5

M34 adds an advanced executor for CLI commands and external programs:

```python
import sys

from pyworkflowkit.adapters.executors.subprocess import (
    SubprocessCommand,
    SubprocessExecutor,
)


def command() -> SubprocessCommand:
    return SubprocessCommand(
        argv=(sys.executable, "-c", "print('hello from external program')"),
    )


executor = SubprocessExecutor(max_workers=4)
```

The command boundary is explicit:

```text
Python command factory
        ↓
SubprocessCommand(argv=...)
        ↓
Popen(..., shell=False)
        ↓
stdout / stderr / returncode
        ↓
SubprocessResult
        ↓
TaskResult
```

`shell=True` is not exposed by the adapter. Command arguments are passed as an argv
sequence, so shell metacharacters such as `;`, `&&`, and `$()` remain ordinary
arguments instead of becoming shell syntax.

A successful command returns a `SubprocessResult` containing the exact argv, return
code, stdout, and stderr. A non-zero exit raises `SubprocessExecutionError` with the
captured evidence and retry category `subprocess_exit`.

The executor declares:

```text
parallelism   = true
async         = false
timeout       = hard
cancellation  = hard
```

Hard timeout and cancellation apply to the directly owned child process. M36 adds
executable/cwd/environment guardrails plus captured-output boundary limits, while
process-tree sandboxing and operating-system resource quotas remain outside the core.

`SubprocessExecutor` remains an advanced module import and is not added to the
package-root API.

## Observability plugins in 0.5

M35 turns the existing runtime-event extension category into a typed observability
boundary:

```python
from dataclasses import dataclass, field

from pyworkflowkit.domain.runtime import RuntimeEvent


@dataclass
class MyEventSink:
    name: str = "my-events"
    events: list[RuntimeEvent] = field(default_factory=list)

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)


runtime.register_event_sink(MyEventSink())
```

The ordering invariant is deliberate:

```text
state transition
      ↓
UnitOfWork
      ↓
RuntimeEvent persisted
      ↓
COMMIT succeeds
      ↓
ObservabilityDispatcher
      ↓
RuntimeEventSink(s)
```

The durable `RuntimeEvent` history remains the source of truth. Event sinks are
secondary projections that can translate the committed stream into external logs,
metrics, traces, dashboards, or vendor-specific telemetry.

Sink fan-out is deterministic by sink name. A sink exception is isolated, recorded in
`runtime.observability_failures`, and logged; it does not roll back committed runtime
state or change the workflow outcome.

The existing plugin category remains:

```text
PluginType.EVENT
entry-point group: pyworkflowkit.events
factory result: RuntimeEventSink
```

M35 does not add a dependency on OpenTelemetry, Prometheus, Datadog, or another
observability backend.

## Security hardening in 0.5

M36 adds explicit guardrails around the two extension boundaries most likely to leak
privilege or sensitive information: external subprocess execution and observability
export.

### Subprocess policy

```python
import sys

from pyworkflowkit.adapters.executors.subprocess import (
    SubprocessExecutor,
    SubprocessSecurityPolicy,
)

policy = SubprocessSecurityPolicy(
    allowed_executables=frozenset({sys.executable}),
    allowed_env_keys=frozenset({"LANG"}),
    inherit_environment=False,
    max_stdin_bytes=1_048_576,
    max_stdout_bytes=10_485_760,
    max_stderr_bytes=10_485_760,
)

executor = SubprocessExecutor(
    max_workers=4,
    security_policy=policy,
)
```

The default policy does **not** inherit the parent process environment. Explicit
allowlists can further restrict executables, working-directory roots, and environment
keys.

Security-policy violations are normalized as:

```text
SubprocessSecurityError
error_category = security_policy
```

PyWorkflowKit still does **not** claim operating-system sandboxing, CPU/RAM/network
quotas, privilege dropping, seccomp, container isolation, or safe execution of untrusted
Python handlers.

### Observability redaction

Committed RuntimeEvents remain unchanged in durable metadata. Before an event crosses
into an external `RuntimeEventSink`, sensitive-looking payload keys such as
`password`, `token`, `secret`, `api_key`, and authorization/credential fields are
recursively replaced with `<redacted>` by default.

```text
durable RuntimeEvent
        ↓
ObservabilitySecurityPolicy
        ↓
redacted projection
        ↓
external sink
```

Sink exception messages are also redacted by default. An explicit debugging policy can
opt into bounded error-message exposure.

### Release security gates

The CI security job now checks:

```text
Bandit
pip-audit
detect-secrets
dependency review (pull requests; active when GitHub Dependency Graph is enabled)
```

Bandit, pip-audit, and detect-secrets are blocking CI gates. Dependency Review is
configured for pull requests; until GitHub Dependency Graph is enabled for the
repository, CI emits an explicit warning instead of treating platform unavailability as
a dependency vulnerability.

These checks complement — not replace — code review, trusted plugin selection, operating
system isolation, and external secret-management systems.

## Recovery foundation in 0.6.0a1

M37 starts the recovery line by classifying **persisted evidence** rather than silently
changing runtime state.

```python
assessment = runtime.recovery_assessment(
    run_id,
    stale_after_seconds=300,
)

print(assessment.liveness)
print(assessment.resume_eligibility)
print(assessment.reasons)
```

The diagnostic pipeline is:

```text
persisted WorkflowRun
        ↓
TaskRuns / Attempts / Events / ExternalRunRefs
        ↓
latest durable evidence timestamp
        ↓
RecoveryInspector
        ↓
TERMINAL / ACTIVE / STALE_CANDIDATE / UNKNOWN
        ↓
NOT_ELIGIBLE / ELIGIBLE / REQUIRES_RECONCILIATION
```

A stale threshold is a **candidate detector**, not proof that a workload stopped.
M37 therefore never changes WorkflowRun, TaskRun, or TaskAttempt state.

When persisted evidence still contains a `RUNNING` TaskRun, a `RUNNING` TaskAttempt,
or external work attached to a non-terminal task, the assessment is
`REQUIRES_RECONCILIATION`. M38 owns the future reconciliation decision.

For idempotency, M37 exposes the stable `task_run_id` as the technical
`idempotency_key` across attempts:

```text
TaskRun task-run-123
    ├── Attempt 1
    ├── Attempt 2
    └── Attempt 3

idempotency_key = task-run-123
```

M37 deliberately does not add heartbeats, leases, worker ownership, remote status
mutation, or resume execution.

## Reconciliation in 0.6.0a2

M38 consumes the ambiguous recovery evidence identified by M37 and verifies
`ExternalRunRef` values through explicit provider-specific adapters.

```python
from pyworkflowkit.ports.reconciliation import ExternalRunStatus


class MyVerifier:
    provider = "my-provider"

    def verify(self, external_ref):
        # Query the external system using external_ref.external_run_id.
        return ExternalRunStatus.SUCCEEDED


runtime.register_external_run_verifier(MyVerifier())
report = runtime.reconcile_run(run_id, stale_after_seconds=300)
```

The reconciliation flow is:

```text
M37 STALE_CANDIDATE
        ↓
non-terminal TaskRun
        ↓
ExternalRunRef lookup
        ↓
provider verifier
        ↓
normalized external status
        ↓
M38 disposition
   ├── CONFIRMED_SUCCEEDED
   ├── CONFIRMED_FAILED
   ├── CONFIRMED_CANCELLED
   ├── STILL_RUNNING
   └── MANUAL_REQUIRED
```

M38 remains read-only. It does not change WorkflowRun, TaskRun, or TaskAttempt state.
That mutation boundary belongs to M39 — Resume.

Conservative handling is intentional:

```text
missing verifier       → MANUAL_REQUIRED
verification failure   → MANUAL_REQUIRED
UNKNOWN / NOT_FOUND    → MANUAL_REQUIRED
conflicting statuses   → MANUAL_REQUIRED
local RUNNING work
without external proof → MANUAL_REQUIRED
```

Provider exception messages are not copied into the reconciliation report; only the
exception type is retained as diagnostic evidence.

## Same-run resume in 0.6.0a3

M39 turns recovery evidence into controlled continuation of the **same**
`WorkflowRun`.

```python
resumed = runtime.resume_run(
    workflow,
    run_id,
    stale_after_seconds=300,
)
```

The semantic distinction is explicit:

```text
resume
    same WorkflowRun
    same TaskRun identities
    preserve completed tasks
    new TaskAttempt only for remaining work

rerun
    new WorkflowRun
    same WorkflowDefinition

replay
    new WorkflowRun
    historical inputs/references
```

A durable resume pipeline now looks like:

```text
persisted RUNNING WorkflowRun
        ↓
M37 stale-candidate assessment
        ↓
M38 external reconciliation
        ↓
M39 apply reconciled state
        ↓
reload durable dependency outputs
        ↓
execute only PENDING / READY work
        ↓
same WorkflowRun reaches terminal state
```

### Durable task-output checkpoints

A successful task may feed a downstream task through `RunContext.dependency_outputs`.
After a process restart that in-memory Python value no longer exists.

M39 therefore checkpoints **small strict JSON-portable outputs** in
`task_output_checkpoints` when a task succeeds:

```text
TaskResult.output
      ↓
portable JSON validation
      ↓
task_output_checkpoints
      ↓
process restart
      ↓
resume
      ↓
RunContext.dependency_outputs
```

`None` is a valid checkpointed output; row presence distinguishes it from a missing
checkpoint.

A nonportable Python object may still be used during the original in-process run, but it
is not silently pickled or stringified for recovery. If remaining work depends on such
an output after a crash, M39 raises `ResumeError` instead of re-executing the completed
producer or fabricating a value.

### Reconciliation application

M39 consumes M38 dispositions conservatively:

```text
CONFIRMED_SUCCEEDED
    → existing RUNNING attempt/task become SUCCEEDED

CONFIRMED_FAILED
    → existing attempt/task fail
    → fail-fast propagation
    → same WorkflowRun FAILED

CONFIRMED_CANCELLED
    → existing attempt/task cancelled
    → remaining undispatched work cancelled
    → same WorkflowRun CANCELLED

STILL_RUNNING
MANUAL_REQUIRED
    → ResumeError
    → no resume
```

A reconciled external success does not invent a Python output checkpoint. If a
downstream task needs that unavailable value, resume remains blocked unless the workload
communicates through durable references/artifacts instead.

### Event continuity

Resume does not start a second event stream. `RuntimeEventFactory` continues after the
highest persisted event sequence:

```text
before crash: 1 2 3 4
resume:                 5 6 7 ...
```

No new recovery-specific RuntimeEvent enum is introduced; existing events carry a
`recovery` payload marker.

M39 does not add a scheduler, background recovery daemon, heartbeat, lease, or distributed
ownership protocol. Recovery remains an explicit runtime action.

## Non-blocking retry in 0.6.0a4

M40 replaces blocking retry sleeps in the concurrent/long-lived runtime with an explicit
durable eligibility timestamp:

```text
Attempt N fails
      ↓
RetryEngine
      ↓
delay_seconds
      ↓
retry_eligible_at = failed_at + delay
      ↓
persist FAILED TaskAttempt + TASK_RETRYING
      ↓
ConcurrentRunner keeps coordinating other work
      ↓
retry deadline becomes due
      ↓
Attempt N+1
```

The retry decision still belongs to `RetryEngine`. M40 changes **when the coordinator
dispatches the next attempt**, not the retry policy itself.

### Runtime state

No new lifecycle enum is introduced. Between attempts:

```text
TaskRun       = RUNNING
Attempt N     = FAILED
retry_eligible_at = T
Attempt N+1   = not created yet
```

Once `T` is reached, the next `TaskAttempt` is created on the same `TaskRun`.

### Concurrent coordination

`ConcurrentRunner` no longer calls `Sleeper.sleep()` for retry backoff. It combines:

```text
active execution timeout deadlines
+
pending retry deadlines
+
cancellation polling
```

inside the existing completion-queue wait loop.

That means an unrelated READY task can use capacity while another task is waiting for
its retry eligibility:

```text
A attempt 1 FAILED
      │
      └──── retry waiting ─────────────┐
                                      │
B READY → RUNNING → SUCCEEDED          │
                                      │
                         deadline due ─┘
                                      ↓
                               A attempt 2
```

The in-process coordinator uses a monotonic deadline for reliable local waiting, while
the persisted recovery contract uses the timezone-aware wall-clock
`retry_eligible_at`.

### Sequential runtime

The simple sequential `Runner` deliberately keeps its blocking `Sleeper` behavior.
It now persists `retry_eligible_at` before sleeping, so a process crash during that
backoff remains recoverable.

This keeps the sequential API simple while satisfying the M40 requirement specifically
for the concurrent/long-lived runtime.

### Recovery after a crash during backoff

A durable retry wait is explicit recovery evidence:

```text
WorkflowRun RUNNING
TaskRun A RUNNING
Attempt 1 FAILED
retry_eligible_at = T
TASK_RETRYING persisted
        ↓
process exits
```

M37 interprets it as:

```text
now < T
    → ACTIVE
    → retry_wait_not_yet_eligible

now >= T and durable evidence is stale
    → STALE_CANDIDATE
    → ELIGIBLE
```

For a pure local retry wait, M38 does not classify the RUNNING TaskRun as ambiguous work,
because the runtime already knows why it remains RUNNING. If the non-terminal task also
has `ExternalRunRef` evidence, reconciliation remains mandatory; a retry deadline never
suppresses unresolved external side effects.

M39 can resume the same run directly as Attempt N+1 once the retry is eligible and no
other recovery ambiguity remains.

### Persistence

M40 adds Alembic revision:

```text
0001_runtime_metadata
        ↓
0002_task_output_checkpoints
        ↓
0003_retry_eligible_at
```

The new `task_attempts.retry_eligible_at` column is nullable and keeps existing attempt
history backward-compatible.

M40 does **not** add a scheduler, background daemon, lease service, distributed timer,
or new lifecycle status.

## CLI

Both console names currently route to the same CLI:

```bash
pyworkflow --help
pyworkflowkit --help
```

Core commands:

```text
validate
plan
run
inspect
events
manifest
plugins
doctor
version
```

Examples:

```bash
pyworkflow validate myproject.workflows:demo
pyworkflow plan myproject.workflows:demo --json
pyworkflow run myproject.workflows:demo --config pyworkflowkit.toml
pyworkflow plugins --json
pyworkflow doctor --enable executor:custom --json
```

## Runtime configuration

The default local composition is:

```text
LocalExecutor
    +
MemoryMetadataStore
```

A durable SQLite configuration can be supplied with TOML:

```toml
[runtime]
workspace = ".pyworkflow"

[metadata]
backend = "sqlite"
sqlite_path = "state/pyworkflow.sqlite3"
sqlite_wal = true
```

Configuration precedence is:

```text
explicit overrides
    >
TOML configuration
    >
environment variables
    >
defaults
```

## Runtime evidence

PyWorkflowKit separates queryable runtime state from portable evidence:

```text
MetadataStore
    !=
RunManifest
```

A run can expose:

- persisted workflow/task/attempt state;
- ordered runtime events;
- artifact references;
- external-run references;
- deterministic execution lineage;
- a canonical, schema-versioned `RunManifest`.

## Plugin model

The `0.3` plugin foundation supports explicit categories:

```text
executor
metadata
workload
event
```

Entry-point discovery is metadata-first and opt-in. Discovering an installed plugin does
not import or enable it. Compatibility is checked only when explicitly enabled.

## PyIngestKit integration boundary

PyWorkflowKit treats one PyIngestKit job as one atomic workload:

```text
PyWorkflowKit Task
        ↓
PyIngestKit adapter
        ↓
PyIngestKit Job
        ↓
TaskResult + ExternalRunRef
```

The PyWorkflowKit core does not import `pyingestkit` and does not reproduce ingestion
semantics such as Source → RAW → Dataset → Quality. Exactly one runtime owns retries.

## Quality gates

Run the local qualification suite with:

```bash
ruff check .
ruff format --check .
mypy src
pytest --cov=pyworkflowkit --cov-branch
python -m build
pytest tests/reference -q
```

CI qualifies Python 3.11, 3.12, and 3.13, performs wheel installation smoke tests, and
runs the PostgreSQL persistence contract.

## Architecture

```text
WorkflowDefinition
        ↓
DependencyGraph
        ↓
DAGValidator
        ↓
ExecutionPlanner
        ↓
Runner / ConcurrentRunner
        ↓
LocalExecutor / ThreadExecutor + RetryEngine
        ↓
MetadataStore + RuntimeEvents
        ↓
Manifest + Lineage
```

The central design rule remains:

> **PyWorkflowKit owns reliable execution of a generic dependency graph, not the world
> around it.**

Scheduling, distributed workers, web UI, RBAC, multi-tenant governance, and enterprise
control-plane concerns remain outside the core.

## Roadmap

```text
0.1  Core sequential runtime
0.2  Durable persistence and evidence
0.3  Developer framework, CLI, plugins, PyIngestKit boundary
0.4  Bounded concurrency, cancellation, timeout                 ✓ stable
0.5  Process/async/subprocess executors and hardening            ✓ stable
0.6  Recovery, reconciliation, resume, non-blocking retry         ← current development
0.7–0.9  Compatibility and stabilization
1.0  Stable embedded runtime
```

The 0.5 development sequence progressed through ProcessExecutor, AsyncExecutor,
SubprocessExecutor, Observability Plugins, and Security Hardening before transverse
qualification promoted the line to **0.5.0 stable**.

The 0.6 development line now contains **M37 — Recovery Foundation**,
**M38 — Reconciliation**, **M39 — Resume**, and **M40 — Non-blocking Retry** at
**0.6.0a4**. M40 is the final functional milestone of the line; the next step is
transverse qualification for **0.6.0 stable**.
