# Persistence and Evidence

The default metadata backend is `memory`. Use SQLite when runs must survive the lifetime
of one Python process.

A complete executable example is:

```text
examples/02_sqlite_persistence.py
```

## Configure SQLite through the public settings facade

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

Relative SQLite paths are resolved below `runtime.workspace`.

## Reopen a run

```python
from pyworkflowkit import WorkflowRuntime


runtime = WorkflowRuntime(settings)
run = runtime.run(definition)

reopened = WorkflowRuntime(settings)
loaded = reopened.get_run(run.run_id)
events = reopened.events(run.run_id)
manifest = reopened.manifest(definition, run.run_id)
```

The metadata store is the durable source for workflow/task/attempt state and runtime
events.

## Evidence surfaces

The public runtime provides:

```text
get_run(run_id)
events(run_id)
manifest(workflow, run_id)
lineage(workflow, run_id)
inspect_runtime(workflow, run_id)
```

Use `manifest` for portable terminal execution evidence and `events` for the ordered
runtime history.

## PostgreSQL

PostgreSQL support is optional:

```bash
python -m pip install "pyworkflowkit[postgres]"
```

The PostgreSQL DSN is sensitive configuration and is represented through the validated
runtime settings model.
