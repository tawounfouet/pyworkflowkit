"""Canonical durable SQLite metadata example."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from pyworkflowkit import RuntimeSettings, TaskHandle, WorkflowRuntime, task, workflow


@task
def persist_me() -> str:
    return "durable"


@workflow(id="examples.sqlite", version="1")
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
    runtime.register(persist_me.handler_ref, persist_me.handler)

    definition = demo.build()
    run = runtime.run(definition)

    reopened = WorkflowRuntime(settings)
    loaded = reopened.get_run(run.run_id)

    print(
        json.dumps(
            {
                "database_exists": (workspace / "runtime.sqlite3").is_file(),
                "reopened_status": loaded.status.value,
            },
            sort_keys=True,
        )
    )
