# 12 — SQLite Persistence

## What you will learn

You will configure a durable local metadata store and reopen a workflow run from another
runtime instance.

## Install

SQLite support is part of the core installation:

```bash
python -m pip install pyworkflowkit
```

## Configure through the public settings facade

```python
from pathlib import Path

from pyworkflowkit import RuntimeSettings


settings = RuntimeSettings.load(
    overrides={
        "runtime": {"workspace": Path(".pyworkflow")},
        "metadata": {
            "backend": "sqlite",
            "sqlite_path": "runtime.sqlite3",
        },
    }
)
```

Relative SQLite paths are resolved from the runtime workspace.

## Run and reopen

```python
from pyworkflowkit import WorkflowRuntime


runtime = WorkflowRuntime(settings)
for handle in demo.task_handles():
    runtime.register(handle.handler_ref, handle.handler)

definition = demo.build()
run = runtime.run(definition)

reopened = WorkflowRuntime(settings)
loaded = reopened.get_run(run.run_id)
events = reopened.events(run.run_id)
manifest = reopened.manifest(definition, run.run_id)

print(loaded.status)
print(len(events))
print(manifest.status)
```

This is the key difference from memory persistence: another runtime instance can inspect
the same durable state.

## TOML equivalent

Create `pyworkflowkit.toml`:

```toml
[runtime]
workspace = ".pyworkflow"

[metadata]
backend = "sqlite"
sqlite_path = "runtime.sqlite3"
sqlite_busy_timeout_ms = 5000
sqlite_wal = true
```

Then CLI commands in separate processes can share the same run database.

## CLI flow

```bash
pwk run workflow:demo --config pyworkflowkit.toml --json
pwk inspect <RUN_ID> --config pyworkflowkit.toml
pwk events <RUN_ID> --config pyworkflowkit.toml
```

## Common mistakes

- using the memory backend for multi-process CLI inspection;
- assuming a relative path is independent from `runtime.workspace`;
- deleting the SQLite file and expecting historical runs to remain;
- putting application-domain records into the workflow metadata database by default.

## Exercises

1. Execute one workflow with SQLite.
2. Close the process.
3. Load the run from a new process.
4. Compare `events` and `manifest` after reopening.

## Related example

Canonical companion: [`examples/12_sqlite.py`](../../examples/12_sqlite.py).

The historical `examples/02_sqlite_persistence.py` example remains available for compatibility.

## Next chapter

Continue with [13 — PostgreSQL Persistence](13_POSTGRESQL_PERSISTENCE.md).
