# 15 — CLI Zero to Hero

## What you will learn

You will operate the local workflow lifecycle with the canonical `pwk` command, from
validation through manifest inspection.

## Command identity

```text
canonical       pwk
long alias      pyworkflowkit
compatibility   pyworkflow
```

All three commands share the same command set and machine behavior. New documentation uses
`pwk`.

## Workflow target

CLI workflows use:

```text
module:attribute
```

Example:

```text
examples.getting_started_workflow:demo
```

## 1. Version

```bash
pwk version
```

## 2. Validate

```bash
pwk validate examples.getting_started_workflow:demo
```

Machine mode:

```bash
pwk validate examples.getting_started_workflow:demo --json
```

## 3. Plan

```bash
pwk plan examples.getting_started_workflow:demo
```

The human path uses a Rich tree. Automation uses:

```bash
pwk plan examples.getting_started_workflow:demo --json
```

## 4. Configure durable state

```toml
[runtime]
workspace = ".pyworkflow-demo"

[metadata]
backend = "sqlite"
sqlite_path = "runtime.sqlite3"
sqlite_wal = false
```

Durability matters because `run`, `inspect`, `events`, and `manifest` may execute as
separate processes.

## 5. Run

```bash
pwk run \
  examples.getting_started_workflow:demo \
  --config pyworkflowkit.toml \
  --json
```

Capture the returned `run_id`.

## 6. Inspect

```bash
pwk inspect <RUN_ID> --config pyworkflowkit.toml
pwk events <RUN_ID> --config pyworkflowkit.toml
pwk manifest \
  examples.getting_started_workflow:demo \
  <RUN_ID> \
  --config pyworkflowkit.toml
```

## 7. Plugins and diagnostics

```bash
pwk plugins
pwk doctor
```

Use `--json` for machine-facing integration.

## Human vs machine contract

```text
human mode
    Rich presentation
    optimized for reading

--json
    stable machine payload
    optimized for automation
```

Never scrape the human Rich output in scripts.

## Common mistakes

- running with memory metadata and expecting a later CLI process to find the run;
- parsing human output;
- importing a workflow module with side effects;
- using the historical aliases in new documentation when `pwk` is available.

## Exercises

1. Validate and plan the same workflow in human and JSON modes.
2. Execute with SQLite.
3. Inspect events and manifest by run ID.
4. Compare `pwk version`, `pyworkflowkit version`, and `pyworkflow version`.

## Related example

CLI-oriented executable examples are completed in DX04.

## Related notebook

CLI packaging and exit-code behavior remain guide/script topics rather than notebook-first
topics.

## Next chapter

The next DX03 chapter is `16_CONCURRENCY.md`.
