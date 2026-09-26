# PyWorkflowKit

**Reliable workflows without running a workflow platform.**

PyWorkflowKit is an embedded Python workflow runtime for defining, validating, planning,
executing, persisting, inspecting, and evidencing generic dependency graphs of trusted
Python workloads without requiring a scheduler, server, worker cluster, or orchestration
platform.

> **Status:** stable release `0.4.0`.
> The runtime now supports bounded concurrent DAG execution through `ThreadExecutor`
> and `ConcurrentRunner`, plus graceful cancellation and explicit timeout semantics.

## What 0.4 provides

The `0.4.x` line keeps the complete local developer framework from 0.3 and adds
bounded concurrent execution:

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
- timeout failures normalized through the existing retry engine.

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
0.5  Process/async/subprocess executors and hardening            ← next development
0.6  Recovery, reconciliation, resume, non-blocking retry
0.7–0.9  Compatibility and stabilization
1.0  Stable embedded runtime
```

The next implementation milestone after the 0.4 release is **M32 — ProcessExecutor**.
