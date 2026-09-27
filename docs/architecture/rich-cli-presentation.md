# PyWorkflowKit Rich CLI Presentation

Status: DX02 — 1.1.0a2

## Objective

DX02 adds a Rich-based presentation layer for human terminal use while preserving CLI
Machine Contract v1 exactly for automation.

The CLI remains a local operational interface. Rich presentation does not add scheduler,
server, worker, control-plane, or platform responsibilities.

## Output boundary

```text
command
   ↓
domain/application result
   ↓
stable payload
   ├── --json → machine JSON
   └── human  → Rich presentation
```

The machine path owns:

- JSON keys and nested shapes;
- stdout/stderr placement;
- application exit codes;
- deterministic serialization.

The human path owns only presentation.

## Internal layout

```text
src/pyworkflowkit/
├── cli.py
└── cli_rendering/
    ├── __init__.py
    ├── console.py
    ├── formatting.py
    ├── tables.py
    └── trees.py
```

`pyworkflowkit.cli_rendering` is internal and is not part of the frozen public Python API.

## Human renderers

DX02 applies presentation according to the information shape:

| Command | Human representation |
|---|---|
| `validate` | validation summary panel |
| `plan` | execution-plan tree |
| `run` | workflow-run summary panel |
| `inspect` | persisted-run summary panel |
| `events` | event table |
| `manifest` | manifest summary panel |
| `plugins` | plugin table / empty-state message |
| `doctor` | health summary and diagnostics table |

`version` remains plain single-line text because its existing CLI v1 behavior is useful
to both humans and shell scripts.

## Error rendering

Without `--json`, handled CLI errors use Rich stderr presentation.

With `--json`, the existing error object remains unchanged:

```json
{"error":"...","exit_code":2}
```

## Security and trust

Dynamic identifiers and values are emitted as Rich `Text` rather than interpolated
markup. Runtime values therefore cannot inject Rich formatting directives into the
presentation layer.

## Dependency contract

Because PyWorkflowKit imports Rich directly, Rich is a direct runtime dependency:

```text
rich>=13.8,<16
```

The dependency is recorded in both `pyproject.toml` and Distribution Contract v1.

## Qualification

DX02 acceptance requires:

- Rich human output for every supported human renderer;
- no ANSI/Rich content in `--json`;
- CLI Machine Contract v1 tests unchanged;
- exit-code behavior unchanged;
- stderr behavior for machine errors unchanged;
- clean wheel/sdist installation;
- Python 3.11, 3.12, and 3.13 qualification.
