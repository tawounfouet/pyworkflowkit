# PyWorkflowKit

**Reliable workflows without running a workflow platform.**

PyWorkflowKit is an embedded Python workflow runtime for defining, validating, planning, executing, and evidencing generic dependency graphs of trusted Python workloads without requiring a scheduler, server, worker cluster, or orchestration platform.

> **Status:** `0.1.0a1` alpha. The core sequential runtime is qualified, but the public API is still expected to evolve before 1.0.

## What 0.1 provides

The `0.1.x` line is intentionally small and local-first:

- immutable `WorkflowDefinition` and `TaskDefinition` values;
- deterministic DAG validation and topological planning;
- explicit workflow/task/attempt state machines;
- synchronous trusted-Python execution through `LocalExecutor`;
- transactional in-memory runtime metadata through `MemoryMetadataStore`;
- retry policies with deterministic backoff;
- fail-fast propagation with explicit skip reasons;
- ordered runtime events;
- artifacts and external-run references;
- deterministic, schema-versioned `RunManifest` execution evidence.

The current runtime is sequential. Execution groups express structural parallelism, but concurrent dispatch is a later milestone.

## Non-goals of 0.1

The alpha does not provide:

- cron or scheduling;
- a long-running control plane;
- durable SQLite/PostgreSQL persistence;
- CLI/decorator DX;
- plugin discovery;
- concurrent/process/async executors;
- hard timeout/cancellation isolation;
- crash recovery/resume;
- distributed workers.

These belong to later release lines.

## Development setup

PyWorkflowKit requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run all quality gates:

```bash
ruff check .
ruff format --check .
mypy src
pytest --cov=pyworkflowkit --cov-branch
python -m build
```

Run only the V0.1 reference workflows:

```bash
pytest tests/reference -q
```

## Hello world

A complete executable example lives in:

```text
examples/00_hello_world.py
```

Run it with:

```bash
python examples/00_hello_world.py
```

The example executes:

```text
fetch
  ↓
transform
```

and prints the final canonical JSON `RunManifest`.

The explicit API used by the alpha looks like this:

```python
from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.ids import TaskId, WorkflowId

workflow = WorkflowDefinition(
    workflow_id=WorkflowId("example"),
    version="1",
    tasks=(
        TaskDefinition(
            task_id=TaskId("fetch"),
            handler_ref="handlers:fetch",
        ),
        TaskDefinition(
            task_id=TaskId("publish"),
            handler_ref="handlers:publish",
            depends_on=(TaskId("fetch"),),
        ),
    ),
)

handlers = HandlerRegistry()
handlers.register("handlers:fetch", lambda: {"rows": 10})
handlers.register("handlers:publish", lambda: None)

store = MemoryMetadataStore()
runner = Runner(
    metadata_store=store,
    handler_registry=handlers,
    executor=LocalExecutor(),
    clock=SystemClock(),
    id_factory=UuidRuntimeIdFactory(),
    sleeper=SystemSleeper(),
)

run = runner.run(workflow)
print(run.status)
```

A smaller ergonomic public facade is intentionally deferred until the API surface is ready to be stabilized.

## Runtime architecture

```text
WorkflowDefinition
        ↓
DependencyGraph
        ↓
DAGValidator
        ↓
ExecutionPlanner
        ↓
ReadyTaskResolver
        ↓
RunStateMachine
        ↓
HandlerRegistry
        ↓
LocalExecutor
        ↓
RetryEngine / FailurePropagator
        ↓
MetadataStore + RuntimeEvents
        ↓
RunManifestBuilder
```

The central design rule is:

> **PyWorkflowKit owns reliable execution of a graph, not the world around it.**

## Repository layout

```text
src/pyworkflowkit/
├── domain/
│   ├── definitions.py
│   ├── graph.py
│   ├── ids.py
│   ├── manifest.py
│   ├── runtime.py
│   └── values.py
├── application/
│   ├── events.py
│   ├── execution.py
│   ├── failure.py
│   ├── manifest.py
│   ├── planning.py
│   ├── retry.py
│   ├── runner.py
│   └── state_machine.py
├── ports/
│   ├── executor.py
│   ├── metadata_store.py
│   └── runtime.py
└── adapters/
    ├── executors/
    ├── metadata/
    └── runtime.py

tests/
├── unit/
├── contract/
├── property/
└── reference/

examples/
└── 00_hello_world.py
```

## V0.1 acceptance baseline

The `tests/reference/` suite freezes the observable semantics of the first runtime line, including:

```text
single task success
linear dependency execution
deterministic sequential diamond
retry then success
retry exhaustion
dependency-failure propagation
fail-fast abort
portable deterministic manifest
sensitive-value redaction
invalid cycle rejected before runtime creation
```

These scenarios are a release gate in CI.

## Release direction

```text
0.1.x  Sequential in-memory runtime
0.2.x  Durable persistence & execution evidence
0.3.x  Developer experience & extensibility
0.4.x  Concurrency foundations
0.5.x  Hardening & integration
0.6.x  Recovery / resume / reconciliation
1.0    Stable embedded workflow runtime
```

## License

No open-source license has been selected yet. Until a license is explicitly added, the repository should not be assumed to grant reuse rights beyond GitHub's normal viewing/forking mechanics.
