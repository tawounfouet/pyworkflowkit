"""LOT-12 durable SQLite evidence acceptance after process/store restart."""

from __future__ import annotations

from pathlib import Path

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.migrations import MIGRATION_HEAD_REVISION
from pyworkflowkit.persistence import SQLiteMetadataStore
from pyworkflowkit.runtime import WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus


def test_sqlite_restart_preserves_outputs_events_manifest_and_lineage(
    tmp_path: Path,
) -> None:
    database = tmp_path / "lot12.sqlite3"
    workflow = WorkflowDefinition(
        name="lot12-restart",
        tasks=(
            TaskDefinition(key="extract", workload=lambda: {"rows": 3}),
            TaskDefinition(
                key="load",
                workload=lambda: {"loaded": 3},
                dependencies=("extract",),
            ),
        ),
    )

    with SQLiteMetadataStore(database, wal=False) as store:
        runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
        result = runtime.run(workflow)
        run_id = result.run_id

        before_events = runtime.events(run_id)
        before_manifest = runtime.manifest(run_id, require_terminal=True)
        before_lineage = runtime.lineage(workflow, run_id)

        assert result.status is WorkflowRunStatus.SUCCEEDED
        assert store.metadata().schema_version == MIGRATION_HEAD_REVISION
        assert MIGRATION_HEAD_REVISION == "0005_v2_task_output_checkpoints"

    with SQLiteMetadataStore(database, wal=False) as reopened:
        runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=reopened)

        after_events = runtime.events(run_id)
        after_manifest = runtime.manifest(run_id, require_terminal=True)
        after_lineage = runtime.lineage(workflow, run_id)

        assert after_events == before_events
        assert after_manifest == before_manifest
        assert after_lineage == before_lineage
        assert tuple(task.output_digest for task in after_manifest.tasks) == tuple(
            task.output_digest for task in after_lineage.tasks
        )
        assert all(task.output_digest is not None for task in after_manifest.tasks)
