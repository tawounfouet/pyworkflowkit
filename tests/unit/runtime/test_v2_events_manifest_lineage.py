"""LOT-12 unit acceptance for events, manifests, lineage and durable outputs."""

from __future__ import annotations

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.diagnostics import RuntimeInspector
from pyworkflowkit.errors import MetadataNotFoundError
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.lineage import MANIFEST_SCHEMA_VERSION
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.runtime import RuntimeEventType, WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus


def _workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="lot12",
        tasks=(
            TaskDefinition(
                key="extract",
                workload=lambda: {"rows": [1, 2, 3]},
            ),
            TaskDefinition(
                key="publish",
                workload=lambda: {"published": True},
                dependencies=("extract",),
            ),
        ),
    )


def test_runtime_projects_durable_events_manifest_lineage_and_inspection() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(
        executor=InlineExecutor(),
        metadata=store,
    )
    workflow = _workflow()

    result = runtime.run(workflow)

    assert result.status is WorkflowRunStatus.SUCCEEDED

    events = runtime.events(result.run_id)
    assert events
    assert tuple(event.sequence for event in events) == tuple(
        sorted(event.sequence for event in events)
    )
    assert events[0].event_type is RuntimeEventType.WORKFLOW_STATE_CHANGED
    assert events[-1].event_type is RuntimeEventType.WORKFLOW_STATE_CHANGED
    assert events[-1].to_status == WorkflowRunStatus.SUCCEEDED.value

    manifest = runtime.manifest(result.run_id, require_terminal=True)
    assert manifest.schema_version == MANIFEST_SCHEMA_VERSION == "2"
    assert manifest.workflow_run_id == result.run_id
    assert tuple(task.task_key for task in manifest.tasks) == ("extract", "publish")
    assert all(task.output_digest is not None for task in manifest.tasks)
    assert manifest.tasks[0].output == {"rows": (1, 2, 3)}
    assert manifest.tasks[1].output == {"published": True}
    assert manifest.events == events

    lineage = runtime.lineage(workflow, result.run_id)
    assert lineage.workflow_run_id == result.run_id
    assert tuple(task.task_key for task in lineage.tasks) == ("extract", "publish")
    assert all(task.output_digest is not None for task in lineage.tasks)
    assert len(lineage.dependencies) == 1
    assert lineage.dependencies[0].upstream_task_run_id == lineage.tasks[0].task_run_id
    assert lineage.dependencies[0].downstream_task_run_id == lineage.tasks[1].task_run_id

    inspection = runtime.inspect(workflow, result.run_id)
    assert inspection.event_count == len(events)
    assert inspection.output_checkpoint_count == 2
    assert inspection.deadlocked is False

    direct_inspection = RuntimeInspector(metadata=store).inspect(workflow, result.run_id)
    assert direct_inspection == inspection


def test_nonportable_output_remains_process_local_and_is_not_falsely_durable() -> None:
    class Opaque:
        pass

    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(
        executor=InlineExecutor(),
        metadata=store,
    )
    workflow = WorkflowDefinition(
        name="opaque-output",
        tasks=(TaskDefinition(key="opaque", workload=Opaque),),
    )

    result = runtime.run(workflow)

    assert isinstance(result.task("opaque").output, Opaque)
    assert "PWK-OUTPUT-NONPORTABLE" in {diagnostic.code for diagnostic in result.diagnostics}

    task_run = store.list_task_runs(result.run_id)[0]
    try:
        store.get_task_output_checkpoint(task_run.task_run_id)
    except MetadataNotFoundError:
        pass
    else:  # pragma: no cover - defensive proof
        raise AssertionError("opaque output must not be persisted")

    manifest = runtime.manifest(result.run_id)
    assert manifest.tasks[0].output is None
    assert manifest.tasks[0].output_digest is None
