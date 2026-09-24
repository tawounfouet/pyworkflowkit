# PyWorkflowKit

**Reliable workflows without running a workflow platform.**

PyWorkflowKit is an early-stage Python library for defining, validating, planning, and executing generic dependency graphs of Python workloads without requiring a full workflow platform.

> **Status:** pre-alpha. The runtime API is not yet stable.

## Scope of the first release

The `0.1.x` line is intentionally focused on a small embedded sequential runtime:

- immutable workflow/task definitions;
- deterministic DAG validation and planning;
- explicit runtime state transitions;
- local workload execution;
- in-memory runtime metadata;
- retries and fail-fast semantics;
- runtime events;
- a portable run manifest.

Durable SQL persistence, the CLI, plugins, concurrency, timeout/cancellation orchestration, and recovery are later milestones.

## Development setup

PyWorkflowKit requires Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run the quality checks:

```bash
ruff check .
ruff format --check .
mypy src
pytest
python -m build
```

## Repository layout

The project uses a `src/` layout. Packages are added only when a real implementation responsibility exists; the repository deliberately avoids pre-creating empty architectural layers.

```text
src/
└── pyworkflowkit/
    ├── __init__.py
    └── py.typed

tests/
└── unit/
    └── test_package.py
```

## Architecture direction

The implementation grows from the center outward:

```text
Domain
  ↓
State Machine
  ↓
Dependency Graph / Planner
  ↓
Executor + Memory MetadataStore
  ↓
Mini Runner
  ↓
Retry + Events + Manifest
  ↓
0.1.0
```

## License

No open-source license has been selected yet. Until a license is explicitly added, the repository should not be assumed to grant reuse rights beyond GitHub's normal viewing/forking mechanics.

## Project state

The repository bootstrap is the first implementation milestone. Domain primitives are the next step.
