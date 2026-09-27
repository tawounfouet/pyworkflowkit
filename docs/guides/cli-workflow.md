# CLI Workflow

The CLI is intended for local validation, planning, execution, and inspection.

The canonical console command is `pwk`. `pyworkflowkit` and `pyworkflow` remain supported compatibility aliases.

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
pwk validate examples.getting_started_workflow:demo --json
```

## Plan

```bash
pwk plan examples.getting_started_workflow:demo --json
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
pwk run \
  examples.getting_started_workflow:demo \
  --config pyworkflowkit.toml \
  --json
```

The JSON result contains the `run_id`.

## Inspect

Replace `<RUN_ID>` with the identifier returned by `run`:

```bash
pwk inspect <RUN_ID> --config pyworkflowkit.toml --json
pwk events <RUN_ID> --config pyworkflowkit.toml --json
pwk manifest \
  examples.getting_started_workflow:demo \
  <RUN_ID> \
  --config pyworkflowkit.toml \
  --json
```

## Diagnostics

List discovered plugin entry points without loading them:

```bash
pwk plugins --json
```

Check plugin compatibility:

```bash
pwk doctor --json
```

## Human and machine output

The default terminal experience uses Rich presentation for summaries, tables, and
execution-plan trees:

```bash
pwk plan examples.getting_started_workflow:demo
pwk plugins
pwk doctor
```

Machine-facing automation must continue to use `--json`:

```bash
pwk plan examples.getting_started_workflow:demo --json
```

Rich rendering is never applied to JSON output. CLI JSON keys, streams, and exit codes
remain governed by CLI Machine Contract v1. Scripts should never parse the human-facing
Rich output.
