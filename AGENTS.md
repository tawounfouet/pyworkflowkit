# AGENTS.md

# PyWorkflowKit — Repository Instructions for Coding Agents

This file defines the canonical repository-level instructions for AI coding agents and automated contributors working on PyWorkflowKit.

It applies to the entire repository unless a more specific `AGENTS.md` exists in a subdirectory.

Human-maintained specifications, public contracts, tests, and release evidence remain authoritative over agent assumptions.

---

## 1. Repository identity

```text
Project: PyWorkflowKit
Package: pyworkflowkit
Repository: tawounfouet/pyworkflowkit
Current qualified historical tag: 2.1.0
Current release target: 2.1.1
Current release state: final remediation qualification before external publication
Python support: 3.11 / 3.12 / 3.13
Build tool: hatchling
Package manager: uv
```

PyWorkflowKit is an embedded, resilient Python workflow runtime for defining, validating, planning, executing, persisting, inspecting, and evidencing generic dependency graphs of trusted Python workloads without requiring a scheduler, worker cluster, or orchestration platform.

Canonical V2 execution path:

```text
WorkflowDefinition (TaskDefinition, >> operator)
        ↓
ExecutionPlan (topological DAG validation)
        ↓
WorkflowRuntime
        ↓
Explicit ExecutorAdapter (Inline, Subprocess, Thread, Async, Process)
        ↓
MetadataStore (InMemory, SQLite, PostgreSQL)
        ↓
WorkflowResult, Manifest & Telemetry Spans
```

---

## 2. Non-negotiable architecture invariants

### Core is zero-dependency (except standard typed foundation)
The core package dependencies are strictly limited to runtime essentials declared in `pyproject.toml` (`pydantic`, `rich`, `typer`, `sqlalchemy`, `alembic`).
External drivers and telemetry bridges are optional extras:
- `postgres` = `["psycopg[binary]>=3.2,<4"]`
- `otel` = `["opentelemetry-api>=1.20,<2"]`

### Telemetry imports are deferred and strictly bounded
OpenTelemetry must **never** be imported at the module top level of any core module.
All OpenTelemetry integration is strictly encapsulated within `src/pyworkflowkit/runtime/telemetry.py`.
Any access occurs via `get_telemetry_bridge()` or explicit `TelemetryBridge` injection.
A missing or failing telemetry provider must **never** disrupt workflow execution.

### Domain definitions are immutable and decoupled from runtime
`WorkflowDefinition` and `TaskDefinition` are frozen dataclasses representing user intention.
They do not contain runtime instances, database connections, or executor subprocesses.
Task dependencies can be authored via constructor `dependencies=(...)` or the ergonomic `task_a >> task_b` shift operator (LOT-32).

### CLI never implements runtime logic directly
`pwk` (and aliases `pyworkflowkit`, `pyworkflow`) is structured as:
```text
Typer = CLI parsing and command routing
Rich = human presentation
CLI Services = coordination (Inspection, Run, Pruning)
Core APIs = semantic authority
```
Human output renders tables and panels; `--json` emits strictly typed, unadorned JSON compliant with the frozen CLI Machine Contract (`CLI_MACHINE_CONTRACT_VERSION = "1"`).

---

## 3. Directory layout & Root fixtures

All standalone integration suites, typing fixtures, and ecosystem templates are unified under `integrations/`:

```text
pyworkflowkit/
├── .github/workflows/          # CI, Release Qualification, and PyPI publish pipelines
├── contracts/                  # Frozen machine contracts (evidence baseline)
├── docs/                       # Architecture specs, guides, plans, and releases
├── examples/                   # Canonical executable examples
├── integrations/               # Standalone test suites, fixtures & ecosystem plugin template
│   ├── ecosystem-template/     # Standalone external plugin SDK template (tested by CI)
│   ├── qualification-integrations/ # Standalone packages for transverse qualification (tested by CI)
│   ├── reference-integrations/ # Independent provider packages for real entry points (tested by CI)
│   └── typing-fixtures/        # Static type check fixtures for public consumer validation
├── notebooks/                  # Interactive tutorial notebooks
├── scripts/                    # Release qualification & verification scripts
├── src/pyworkflowkit/          # Core package source code
└── tests/                      # Architecture, contract, integration, and unit tests
```

> **Important**: All suites under `integrations/` (`reference-integrations`, `qualification-integrations`, `ecosystem-template`, `typing-fixtures`) are standalone test fixtures. They are explicitly excluded from wheels and source distributions (`FORBIDDEN_WHEEL_PREFIXES`, `FORBIDDEN_SDIST_PREFIXES`), but are required by qualification gates (`scripts/qualify_*.py`) and GitHub Actions workflows.

---

## 4. Quality commands & Development workflow

Always use `uv run` with Homebrew PATH priority on macOS:

```bash
export PATH="/opt/homebrew/bin:$PATH"
```

### Fast local iteration
```bash
# Code formatting and linting
uv run ruff check .
uv run ruff format --check .

# Automatic fix
uv run ruff check --fix .
uv run ruff format .

# Strict static typing
uv run mypy src

# Unit and integration test suite
uv run pytest tests/
```

### Full qualification & coverage check
```bash
# Coverage gate (must stay >= 90.0%)
uv run pytest --cov=src/pyworkflowkit --cov-report=term

# Security gates (Bandit and secrets)
uv run --extra security bandit -r src/pyworkflowkit -x src/pyworkflowkit/migrations

# Packaging & distribution qualification
uv build
uv run python scripts/qualify_distribution.py --dist-dir dist
```

---

## 5. Engineering protocol for tasks & LOTs

1. **One dedicated Git branch per LOT/feature**:
   ```bash
   git checkout main && git pull origin main
   git checkout -b <type>/<description>
   ```
2. **Never break existing contracts**:
   Contracts under `contracts/` and tests in `tests/contract/` and `tests/reference/` represent locked compatibility baselines. Never weaken assertions to make a test pass.
3. **Verify all gates before PR**:
   - `ruff check .` + `ruff format --check .`
   - `mypy src` (0 errors)
   - `pytest` with coverage $\ge 90.0\%$
   - Security scan clean (`bandit`, `# nosec` only with explicit justification)
4. **Pull Request & CI**:
   - Create PR with clear summary and validation evidence.
   - Require every mandatory GitHub Actions check for the PR head SHA to pass; never hard-code a historical aggregate check count.
   - Squash & merge to `main`.
