# CLAUDE.md

# PyWorkflowKit — Claude Code Instructions

This file contains Claude Code-specific instructions for PyWorkflowKit.
It is intentionally a thin overlay.

The canonical repository-wide instructions are defined in:

```text
AGENTS.md
```

Claude Code MUST read and follow `AGENTS.md` before making changes.

Authority order:

```text
specifications / contracts / tests
        ↓
AGENTS.md
        ↓
CLAUDE.md
```

---

## 1. Repository context

```text
Project: PyWorkflowKit
Package: pyworkflowkit
Repository: tawounfouet/pyworkflowkit
Current qualified historical tag: 2.1.0
Current release target: 2.1.1
Current release state: final remediation qualification before external publication
Current CLI contract: CLI Machine Contract v1
Python versions: 3.11 / 3.12 / 3.13
```

---

## 2. First action in every coding session

Before editing:

```text
1. Read AGENTS.md.
2. Inspect the current branch and status.
3. Read the relevant specification / plan in docs/plans/.
4. Inspect existing implementation.
5. Inspect adjacent tests.
6. Inspect affected contract snapshots.
7. Only then plan and edit.
```

The live repository is the source of truth.

---

## 3. Architecture invariants

- Keep the dependency direction defined in `AGENTS.md`.
- Never introduce a dependency from Domain/Core toward:
  ```text
  CLI (Typer/Rich)
  Physical database engines directly (use ports & interfaces)
  OpenTelemetry (lazy imports isolated strictly to runtime/telemetry.py)
  ```
- Use public APIs before internals.
- Respect the zero-dependency core model (`postgres` and `otel` are optional extras).

---

## 4. Integrations directory preservation
 
All standalone integration suites, qualification packages, ecosystem templates, and typing fixtures are unified under `integrations/`:
- `integrations/reference-integrations/`
- `integrations/qualification-integrations/`
- `integrations/ecosystem-template/`
- `integrations/typing-fixtures/`
 
They are standalone test suites required by CI qualification gates (`scripts/qualify_*.py`).

---

## 5. Quality commands

Run using `uv run` with Homebrew PATH priority on macOS:

```bash
export PATH="/opt/homebrew/bin:$PATH"

# Linting & Formatting
uv run ruff check .
uv run ruff format --check .

# Static Typing
uv run mypy src

# Tests & Coverage
uv run pytest tests/
uv run pytest --cov=src/pyworkflowkit --cov-report=term

# Security
uv run --extra security bandit -r src/pyworkflowkit -x src/pyworkflowkit/migrations
```

Do not report a command as green unless it was actually executed successfully.

---

## 6. Engineering cycle

```text
inspect
→ implement small coherent change
→ run targeted tests
→ check ruff & mypy
→ run broader regression
→ verify coverage >= 90.0%
→ PR & verify every mandatory CI / Release Qualification check for the exact head SHA
```
