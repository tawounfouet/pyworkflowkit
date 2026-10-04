"""LOT-33 durable SQLite acceptance for V2 selective resume and recovery."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.executors import InlineExecutor, TaskExecutionContext
from pyworkflowkit.migrations import MIGRATION_HEAD_REVISION
from pyworkflowkit.persistence import SQLiteMetadataStore
from pyworkflowkit.runtime import (
    RuntimeEventType,
    WorkflowRuntime,
)
from pyworkflowkit.states import TaskRunStatus, WorkflowRunStatus


def test_sqlite_restart_selective_resume_and_manifest_lineage(tmp_path: Path) -> None:
    database = tmp_path / "resume_acceptance.sqlite3"

    call_counts: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}
    c_should_fail = True

    def workload_a() -> dict[str, int]:
        call_counts["a"] += 1
        return {"records": 100}

    def workload_b(context: TaskExecutionContext) -> dict[str, int]:
        call_counts["b"] += 1
        dep = context.dependency_outputs["task-a"]
        assert isinstance(dep, (dict, Mapping))
        return {"processed": int(dep["records"]) * 2}

    def workload_c(context: TaskExecutionContext) -> dict[str, str]:
        call_counts["c"] += 1
        if c_should_fail:
            raise RuntimeError("Database connection lost during bulk insert")
        dep = context.dependency_outputs["task-b"]
        assert isinstance(dep, (dict, Mapping))
        return {"status": "loaded", "count": str(dep["processed"])}

    def workload_d(context: TaskExecutionContext) -> dict[str, str]:
        call_counts["d"] += 1
        dep = context.dependency_outputs["task-c"]
        assert isinstance(dep, (dict, Mapping))
        return {"notification": f"Pipeline finished: {dep['status']}"}

    workflow = WorkflowDefinition(
        name="etl-pipeline",
        tasks=(
            TaskDefinition(key="task-a", workload=workload_a),
            TaskDefinition(key="task-b", workload=workload_b, dependencies=("task-a",)),
            TaskDefinition(key="task-c", workload=workload_c, dependencies=("task-b",)),
            TaskDefinition(key="task-d", workload=workload_d, dependencies=("task-c",)),
        ),
    )

    # Phase 1: Initial run fails at task-c
    with SQLiteMetadataStore(database, wal=False) as store:
        assert store.metadata().schema_version == MIGRATION_HEAD_REVISION
        assert MIGRATION_HEAD_REVISION == "0005_v2_task_output_checkpoints"

        runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
        initial_result = runtime.run(workflow)
        initial_run_id = initial_result.run_id

        assert initial_result.status is WorkflowRunStatus.FAILED
        assert initial_result.task("task-a").status is TaskRunStatus.SUCCEEDED
        assert initial_result.task("task-b").status is TaskRunStatus.SUCCEEDED
        assert initial_result.task("task-c").status is TaskRunStatus.FAILED
        assert initial_result.task("task-d").status is TaskRunStatus.SKIPPED
        assert call_counts == {"a": 1, "b": 1, "c": 1, "d": 0}

    # Phase 2: Close and reopen metadata store, then resume run
    c_should_fail = False

    with SQLiteMetadataStore(database, wal=False) as reopened_store:
        assert reopened_store.metadata().schema_version == MIGRATION_HEAD_REVISION

        # Verify initial run state is preserved across process restart
        persisted_orig = reopened_store.get_workflow_run(initial_run_id)
        assert persisted_orig.status is WorkflowRunStatus.FAILED
        assert persisted_orig.resume_of_run_id is None

        runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=reopened_store)
        resume_result = runtime.resume_run(initial_run_id, workflow)
        resume_run_id = resume_result.run_id

        assert resume_result.status is WorkflowRunStatus.SUCCEEDED
        assert resume_run_id != initial_run_id

        # Verify call counts: task-a and task-b must NOT be recomputed!
        assert call_counts == {"a": 1, "b": 1, "c": 2, "d": 1}

        # Verify task statuses
        task_a = resume_result.task("task-a")
        task_b = resume_result.task("task-b")
        task_c = resume_result.task("task-c")
        task_d = resume_result.task("task-d")

        assert task_a.status is TaskRunStatus.REUSED
        assert task_a.attempt_ids == ()
        assert task_a.output == {"records": 100}

        assert task_b.status is TaskRunStatus.REUSED
        assert task_b.attempt_ids == ()
        assert task_b.output == {"processed": 200}

        assert task_c.status is TaskRunStatus.SUCCEEDED
        assert len(task_c.attempt_ids) == 1
        assert task_c.output == {"status": "loaded", "count": "200"}

        assert task_d.status is TaskRunStatus.SUCCEEDED
        assert len(task_d.attempt_ids) == 1
        assert task_d.output == {"notification": "Pipeline finished: loaded"}

        # Verify parent workflow link
        persisted_resumed = reopened_store.get_workflow_run(resume_run_id)
        assert persisted_resumed.status is WorkflowRunStatus.SUCCEEDED
        assert persisted_resumed.resume_of_run_id == str(initial_run_id)

        # Verify events
        events = runtime.events(resume_run_id)
        event_types = tuple(e.event_type for e in events)
        assert RuntimeEventType.WORKFLOW_RESUMED in event_types
        assert RuntimeEventType.TASK_RESUMED in event_types

        # Verify manifest and lineage
        manifest = runtime.manifest(resume_run_id, require_terminal=True)
        lineage = runtime.lineage(workflow, resume_run_id)

        assert tuple(t.output_digest for t in manifest.tasks) == tuple(
            t.output_digest for t in lineage.tasks
        )
        assert all(t.output_digest is not None for t in manifest.tasks)


def test_sqlite_restart_selective_resume_with_forced_recomputation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "resume_forced.sqlite3"

    call_counts: dict[str, int] = {"a": 0, "b": 0, "c": 0}
    b_fails = True

    def workload_a() -> dict[str, int]:
        call_counts["a"] += 1
        return {"val": 10}

    def workload_b(context: TaskExecutionContext) -> dict[str, int]:
        call_counts["b"] += 1
        if b_fails:
            raise RuntimeError("b failed")
        dep = context.dependency_outputs["task-a"]
        assert isinstance(dep, (dict, Mapping))
        return {"val": int(dep["val"]) + 5}

    def workload_c(context: TaskExecutionContext) -> dict[str, int]:
        call_counts["c"] += 1
        dep = context.dependency_outputs["task-b"]
        assert isinstance(dep, (dict, Mapping))
        return {"val": int(dep["val"]) * 2}

    wf = WorkflowDefinition(
        name="forced-pipeline",
        tasks=(
            TaskDefinition(key="task-a", workload=workload_a),
            TaskDefinition(key="task-b", workload=workload_b, dependencies=("task-a",)),
            TaskDefinition(key="task-c", workload=workload_c, dependencies=("task-b",)),
        ),
    )

    with SQLiteMetadataStore(database, wal=False) as store:
        runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
        r1 = runtime.run(wf)
        assert r1.status is WorkflowRunStatus.FAILED
        assert call_counts == {"a": 1, "b": 1, "c": 0}

    b_fails = False

    with SQLiteMetadataStore(database, wal=False) as store:
        runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
        # Force recomputing task-a
        r2 = runtime.resume_run(r1.run_id, wf, force_recompute_tasks=["task-a"])
        assert r2.status is WorkflowRunStatus.SUCCEEDED
        # Since task-a was forced, all downstream tasks (task-b, task-c) also recomputed!
        assert call_counts == {"a": 2, "b": 2, "c": 1}
        assert r2.task("task-a").status is TaskRunStatus.SUCCEEDED
        assert r2.task("task-b").status is TaskRunStatus.SUCCEEDED
        assert r2.task("task-c").status is TaskRunStatus.SUCCEEDED
