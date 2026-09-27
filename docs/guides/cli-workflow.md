# CLI Workflow

The CLI is intended for local validation, planning, execution, and inspection.

The canonical console command is `pyworkflow`. `pyworkflowkit` is a supported alias.

## Workflow target format

CLI workflow references use:

```text
module:attribute
```

The repository example is:

```text
examples.getting_started_workflow:demo
```

## Validate

```bash
pyworkflow validate examples.getting_started_workflow:demo --json
```

## Plan

```bash
pyworkflow plan examples.getting_started_workflow:demo --json
```

## Configure SQLite persistence

Commands such as `run` and `inspect` execute in separate processes. Use a durable
backend when later commands need to observe the same run.

Create `pyworkflowkit.toml`:

```toml
[runtime]
workspace = ".pyworkflow-demo"

[metadata]
backend = "sqlite"
sqlite_path = "runtime.sqlite3"
sqlite_wal = false
```

## Run

```bash
pyworkflow run \
  examples.getting_started_workflow:demo \
  --config pyworkflowkit.toml \
  --json
```

The JSON result contains the `run_id`.

## Inspect

Replace `<RUN_ID>` with the identifier returned by `run`:

```bash
pyworkflow inspect <RUN_ID> --config pyworkflowkit.toml --json
pyworkflow events <RUN_ID> --config pyworkflowkit.toml --json
pyworkflow manifest \
  examples.getting_started_workflow:demo \
  <RUN_ID> \
  --config pyworkflowkit.toml \
  --json
```

## Diagnostics

List discovered plugin entry points without loading them:

```bash
pyworkflow plugins --json
```

Check plugin compatibility:

```bash
pyworkflow doctor --json
```

## Machine-facing behavior

CLI JSON keys and exit codes are governed by the existing CLI machine contract v1.
Scripts should prefer `--json` instead of parsing human-readable output.
