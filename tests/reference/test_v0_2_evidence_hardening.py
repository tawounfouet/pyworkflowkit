"""V0.2 evidence-hardening acceptance scenarios."""

from datetime import UTC, datetime

import pytest

from pyworkflowkit.adapters.metadata.sqlite import SQLiteMetadataStore
from pyworkflowkit.application.lineage import ExecutionLineageProjector
from pyworkflowkit.application.manifest import RunManifestBuilder, RunManifestSerializer
from pyworkflowkit.application.manifest_export import RunManifestExporter
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    RuntimeEventType,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import (
    ArtifactId,
    ExternalRunRefId,
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef
from pyworkflowkit.errors import InvalidEventSequenceError

NOW = datetime(2026, 9, 26, 10, 0, tzinfo=UTC)


def workflow_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("evidence"),
        version="1",
        tasks=(
            TaskDefinition(task_id=TaskId("A"), handler_ref="handlers:a"),
            TaskDefinition(
                task_id=TaskId("B"),
                handler_ref="handlers:b",
                depends_on=(TaskId("A"),),
            ),
        ),
    )


def seed_terminal_run(store: SQLiteMetadataStore) -> None:
    run_id = WorkflowRunId("run-evidence")
    task_a_id = TaskRunId("task-run-A")
    task_b_id = TaskRunId("task-run-B")

    with store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=run_id,
                workflow_id=WorkflowId("evidence"),
                workflow_version="1",
                status=WorkflowRunStatus.SUCCEEDED,
                created_at=NOW,
                started_at=NOW,
                finished_at=NOW,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=task_a_id,
                run_id=run_id,
                task_id=TaskId("A"),
                status=TaskRunStatus.SUCCEEDED,
                created_at=NOW,
                started_at=NOW,
                finished_at=NOW,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=task_b_id,
                run_id=run_id,
                task_id=TaskId("B"),
                status=TaskRunStatus.SUCCEEDED,
                created_at=NOW,
                started_at=NOW,
                finished_at=NOW,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("attempt-A-1"),
                task_run_id=task_a_id,
                attempt_number=1,
                status=TaskAttemptStatus.SUCCEEDED,
                started_at=NOW,
                finished_at=NOW,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("attempt-B-1"),
                task_run_id=task_b_id,
                attempt_number=1,
                status=TaskAttemptStatus.SUCCEEDED,
                started_at=NOW,
                finished_at=NOW,
            )
        )
        uow.add_artifact(
            task_run_id=task_a_id,
            artifact=ArtifactReference(
                artifact_id=ArtifactId("artifact-A"),
                name="a.json",
                uri="file:///tmp/a.json",
                metadata={"rows": 2},
            ),
        )
        uow.add_external_run_ref(
            task_run_id=task_b_id,
            external_ref=ExternalRunRef(
                external_ref_id=ExternalRunRefId("external-B"),
                provider="external-system",
                external_run_id="remote-42",
            ),
        )

        event_types = (
            RuntimeEventType.WORKFLOW_STARTED,
            RuntimeEventType.TASK_READY,
            RuntimeEventType.TASK_STARTED,
            RuntimeEventType.TASK_SUCCEEDED,
            RuntimeEventType.TASK_READY,
            RuntimeEventType.TASK_STARTED,
            RuntimeEventType.TASK_SUCCEEDED,
            RuntimeEventType.WORKFLOW_SUCCEEDED,
        )
        for index, event_type in enumerate(event_types, start=1):
            task_run_id = None
            task_id = None
            attempt_number = None
            if 2 <= index <= 4:
                task_run_id = task_a_id
                task_id = TaskId("A")
                if index >= 3:
                    attempt_number = 1
            elif 5 <= index <= 7:
                task_run_id = task_b_id
                task_id = TaskId("B")
                if index >= 6:
                    attempt_number = 1
            uow.add_event(
                RuntimeEvent(
                    event_id=RuntimeEventId(f"event-{index}"),
                    event_type=event_type,
                    run_id=run_id,
                    occurred_at=NOW,
                    event_sequence=index * 10,
                    task_run_id=task_run_id,
                    task_id=task_id,
                    attempt_number=attempt_number,
                )
            )
        uow.commit()


def test_v0_2_evidence_survives_restart_and_is_deterministic(tmp_path) -> None:
    database = tmp_path / "runtime.sqlite3"
    export_path = tmp_path / "manifest.json"
    workflow = workflow_definition()

    with SQLiteMetadataStore(database, wal=False) as store:
        seed_terminal_run(store)

        manifest = RunManifestBuilder(metadata_store=store).build(
            workflow=workflow,
            run_id=WorkflowRunId("run-evidence"),
        )
        canonical_json = RunManifestSerializer().to_json(manifest)
        RunManifestExporter().export_json(manifest, export_path)

        lineage = ExecutionLineageProjector(metadata_store=store).project(
            workflow=workflow,
            run_id=WorkflowRunId("run-evidence"),
        )

    with SQLiteMetadataStore(database, wal=False) as reopened:
        rebuilt = RunManifestBuilder(metadata_store=reopened).build(
            workflow=workflow,
            run_id=WorkflowRunId("run-evidence"),
        )
        rebuilt_json = RunManifestSerializer().to_json(rebuilt)
        rebuilt_lineage = ExecutionLineageProjector(metadata_store=reopened).project(
            workflow=workflow,
            run_id=WorkflowRunId("run-evidence"),
        )

    assert rebuilt_json == canonical_json
    assert export_path.read_text(encoding="utf-8") == canonical_json + "\n"
    assert rebuilt_lineage == lineage
    assert lineage.dependencies[0].upstream_task_run_id == "task-run-A"
    assert lineage.dependencies[0].downstream_task_run_id == "task-run-B"
    assert lineage.tasks[0].artifact_ids == ("artifact-A",)
    assert lineage.tasks[1].external_ref_ids == ("external-B",)


def test_event_sequence_must_increase_but_need_not_be_gapless(tmp_path) -> None:
    database = tmp_path / "events.sqlite3"

    with SQLiteMetadataStore(database, wal=False) as store:
        with store.unit_of_work() as uow:
            uow.add_workflow_run(
                WorkflowRun(
                    run_id=WorkflowRunId("run"),
                    workflow_id=WorkflowId("workflow"),
                    workflow_version="1",
                    created_at=NOW,
                )
            )
            uow.add_event(
                RuntimeEvent(
                    event_id=RuntimeEventId("event-10"),
                    event_type=RuntimeEventType.WORKFLOW_STARTED,
                    run_id=WorkflowRunId("run"),
                    occurred_at=NOW,
                    event_sequence=10,
                )
            )
            uow.add_event(
                RuntimeEvent(
                    event_id=RuntimeEventId("event-20"),
                    event_type=RuntimeEventType.WORKFLOW_STARTED,
                    run_id=WorkflowRunId("run"),
                    occurred_at=NOW,
                    event_sequence=20,
                )
            )
            uow.commit()

        event_sequences = [
            event.event_sequence for event in store.list_events(WorkflowRunId("run"))
        ]
        assert event_sequences == [10, 20]

        with pytest.raises(InvalidEventSequenceError), store.unit_of_work() as uow:
            uow.add_event(
                    RuntimeEvent(
                        event_id=RuntimeEventId("event-15"),
                        event_type=RuntimeEventType.WORKFLOW_STARTED,
                        run_id=WorkflowRunId("run"),
                        occurred_at=NOW,
                        event_sequence=15,
                )
            )
