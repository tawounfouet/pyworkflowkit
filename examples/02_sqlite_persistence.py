"""Public-API SQLite persistence and evidence example."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from pyworkflowkit._compat.v1_root import (
    RuntimeSettings,
    TaskHandle,
    WorkflowRuntime,
    task,
    workflow,
)


@task
def persist_me() -> str:
    return "durable"


@workflow(id="docs.sqlite", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (persist_me,)


with TemporaryDirectory() as directory:
    workspace = Path(directory)
    settings = RuntimeSettings.load(
        overrides={
            "runtime": {"workspace": workspace},
            "metadata": {
                "backend": "sqlite",
                "sqlite_path": "runtime.sqlite3",
                "sqlite_wal": False,
            },
        }
    )

    runtime = WorkflowRuntime(settings)
    for handle in demo.task_handles():
        runtime.register(handle.handler_ref, handle.handler)

    definition = demo.build()
    run = runtime.run(definition)

    reopened = WorkflowRuntime(settings)
    loaded = reopened.get_run(run.run_id)
    events = reopened.events(run.run_id)
    manifest = reopened.manifest(definition, run.run_id)

    print(
        json.dumps(
            {
                "status": loaded.status.value,
                "event_count": len(events),
                "manifest_status": manifest.status,
                "database_exists": (workspace / "runtime.sqlite3").is_file(),
            },
            sort_keys=True,
        )
    )
