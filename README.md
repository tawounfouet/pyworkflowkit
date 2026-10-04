# PyWorkflowKit

**Reliable workflows without running a workflow platform.**

PyWorkflowKit is an embedded, resilient Python workflow engine for defining, validating, planning, executing, persisting, inspecting, and evidencing generic dependency graphs of trusted Python workloads without requiring a scheduler, server daemon, worker cluster, or heavy orchestration platform.

> Status: **PyWorkflowKit 2.0.0 is stable.** V2 execution engine, authoring ergonomics (`>>` operator), CLI v1 contract, selective resume, store pruning, and OpenTelemetry tracing are release-qualified.

---

## Goals

- **Zero Heavy Infrastructure**: Run resilient multi-step DAGs inside existing applications, serverless functions, notebooks, or CLI scripts without Redis, RabbitMQ, Celery, or Airflow.
- **Deterministic & Auditable**: Topologically planned execution with immutable manifests, execution event journals, and dependency lineage.
- **Fail-Safe & Selective Resume**: Safe failure isolation, non-blocking retry policies, and granular resumption of failed runs from portable checkpoints.
- **Plug-and-Play Extensibility**: Modular executors (Inline, Subprocess, Thread, Async, Process), metadata stores (Memory, SQLite, PostgreSQL), and telemetry bridges.
- **Native Distributed Tracing**: 3-level span hierarchy (Workflow → Task → Attempt) with W3C `TRACEPARENT` propagation to external subprocesses.

---

## Canonical V2 Architecture

PyWorkflowKit keeps domain intention strictly separated from physical execution engines and metadata storage:

```text
WorkflowDefinition (TaskDefinition, >> operator)
        ↓
ExecutionPlan (topological DAG validation)
        ↓
WorkflowRuntime
        ↓
Explicit Executor (Inline, Subprocess, Thread, Async, Process)
        ↓
MetadataStore (InMemory, SQLite, PostgreSQL)
        ↓
WorkflowResult, Manifest & Telemetry Spans
```

The package root promotes the primary authoring and execution primitives:

- `WorkflowDefinition`, `TaskDefinition`;
- `WorkflowRuntime`;
- `WorkflowRunId`, `CorrelationId`;
- `WorkflowResult`, `TaskResult`;
- `task`, `workflow` (declarative decorators);
- `executors` namespace (`InlineExecutor`, `SubprocessExecutor`, `ThreadExecutor`, `AsyncExecutor`, `ProcessExecutor`);
- `persistence` namespace (`InMemoryMetadataStore`, `SQLiteMetadataStore`, `PostgreSQLMetadataStore`);
- `telemetry` namespace (`TelemetryBridge`, `get_telemetry_bridge`).

---

## Installation

PyWorkflowKit requires Python 3.11 or newer.

```bash
# Core package
pip install pyworkflowkit

# Optional PostgreSQL persistence
pip install "pyworkflowkit[postgres]"

# Optional OpenTelemetry tracing bridge
pip install "pyworkflowkit[otel]"

# Complete development environment
pip install "pyworkflowkit[dev,security]"
```

---

## Quickstart

### 1. Functional DAG Authoring with the `>>` Operator

```python
from pyworkflowkit import TaskDefinition, WorkflowDefinition, WorkflowRuntime
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.persistence import InMemoryMetadataStore


def extract_data() -> dict[str, int]:
    return {"raw_count": 100}


def transform_data(payload: dict[str, int]) -> dict[str, int]:
    return {"processed_count": payload["raw_count"] * 2}


def load_data(payload: dict[str, int]) -> str:
    return f"Loaded {payload['processed_count']} records"


# Define tasks
extract = TaskDefinition(key="extract", workload=extract_data)
transform = TaskDefinition(key="transform", workload=transform_data)
load = TaskDefinition(key="load", workload=load_data)

# Author DAG dependencies using the ergonomic shift operator
extract >> transform >> load

# Build workflow definition
workflow = WorkflowDefinition(
    name="etl_pipeline",
    tasks=(extract, transform, load),
)

# Execute via embedded runtime
runtime = WorkflowRuntime(
    metadata=InMemoryMetadataStore(),
    executor=InlineExecutor(),
)

result = runtime.run(workflow)
print(f"Workflow status: {result.status.value}")
```

### 2. External Subprocess Workloads & W3C Trace Propagation

```python
from pyworkflowkit import TaskDefinition, WorkflowDefinition, WorkflowRuntime
from pyworkflowkit.executors.subprocess import SubprocessCommand, SubprocessExecutor
from pyworkflowkit.persistence import SQLiteMetadataStore

# Define an external shell-free command
backup_task = TaskDefinition(
    key="db_backup",
    workload=SubprocessCommand(argv=("pg_dump", "-Fc", "production_db")),
)

workflow = WorkflowDefinition(name="maintenance", tasks=(backup_task,))

# Automatically propagates W3C TRACEPARENT / TRACESTATE to the subprocess
runtime = WorkflowRuntime(
    metadata=SQLiteMetadataStore(database_path="runtime.db"),
    executor=SubprocessExecutor(max_workers=2),
)
result = runtime.run(workflow)
```

---

## Command Line Interface (`pwk`)

PyWorkflowKit includes a developer-friendly CLI accessible via `pwk`, `pyworkflowkit`, or `pyworkflow`:

```bash
# Verify environment and system health
pwk doctor

# Statically validate workflow syntax and cycle-free DAG topology
pwk validate examples.getting_started_workflow:demo --json

# Preview topological execution plan and concurrency groups
pwk plan examples.getting_started_workflow:demo --json

# Execute workflow directly from terminal with dry-run or live mode
pwk run examples.getting_started_workflow:demo --dry-run
pwk run examples.getting_started_workflow:demo --store sqlite:///.pwk.db

# Inspect execution run evidence, manifests, and task events
pwk inspect <workflow-run-id> --store sqlite:///.pwk.db --json

# Prune historical completed workflow runs
pwk store prune --older-than 30d --status SUCCEEDED --store sqlite:///.pwk.db
```

---

## Learning Journey & Documentation

Explore the complete learning paths:

- **Zero-to-Hero Guides**: Index available at [`docs/guides/README.md`](https://github.com/tawounfouet/pyworkflowkit/blob/main/docs/guides/README.md).
- **First-Use Getting Started**: Canonical guide at [`docs/guides/getting-started.md`](https://github.com/tawounfouet/pyworkflowkit/blob/main/docs/guides/getting-started.md).
- **Executable Examples**: Full suite indexed at [`examples/README.md`](https://github.com/tawounfouet/pyworkflowkit/blob/main/examples/README.md) (start with [`examples/00_hello_world.py`](https://github.com/tawounfouet/pyworkflowkit/blob/main/examples/00_hello_world.py)).
- **Interactive Notebooks**: Jupyter tutorials indexed at [`notebooks/README.md`](https://github.com/tawounfouet/pyworkflowkit/blob/main/notebooks/README.md).

Recommended curriculum:
- [01 — Installation and First Workflow](https://github.com/tawounfouet/pyworkflowkit/blob/main/docs/guides/01_INSTALLATION_AND_FIRST_WORKFLOW.md)
- [04 — Dependencies and DAG](https://github.com/tawounfouet/pyworkflowkit/blob/main/docs/guides/04_DEPENDENCIES_AND_DAG.md)
- [08 — Failures and Retries](https://github.com/tawounfouet/pyworkflowkit/blob/main/docs/guides/08_FAILURES_AND_RETRIES.md)
- [15 — CLI Zero to Hero](https://github.com/tawounfouet/pyworkflowkit/blob/main/docs/guides/15_CLI_ZERO_TO_HERO.md)
- [19 — Plugins and Ecosystem](https://github.com/tawounfouet/pyworkflowkit/blob/main/docs/guides/19_PLUGINS_AND_ECOSYSTEM.md)
- [99 — Complete Reference Application](https://github.com/tawounfouet/pyworkflowkit/blob/main/docs/guides/99_COMPLETE_REFERENCE_APPLICATION.md)

---

## License

Distributed under the terms of the [Apache License 2.0](https://github.com/tawounfouet/pyworkflowkit/blob/main/LICENSE).
