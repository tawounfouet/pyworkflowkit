"""Reusable PyWorkflowKit V2 MetadataStore behavioral conformance suite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit.errors import (
    DuplicateMetadataError,
    MetadataConflictError,
    MetadataInvariantError,
    MetadataNotFoundError,
)
from pyworkflowkit.persistence import (
    ManifestReference,
    MetadataStore,
    StateEntityType,
)
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    ExternalRunRef,
    RuntimeEventType,
    TaskAttempt,
    TaskAttemptId,
    TaskOutputCheckpoint,
    TaskRun,
    TaskRunId,
    WorkflowRun,
    WorkflowRunId,
)
from pyworkflowkit.states import (
    TaskAttemptStateMachine,
    TaskAttemptStatus,
    TaskRunStateMachine,
    TaskRunStatus,
    WorkflowRunStateMachine,
    WorkflowRunStatus,
)

T0 = datetime(2026, 10, 2, 14, 0, tzinfo=UTC)
T1 = T0 + timedelta(seconds=1)
T2 = T0 + timedelta(seconds=2)
T3 = T0 + timedelta(seconds=3)


def workflow_run(run_id: str = "W-1") -> WorkflowRun:
    return WorkflowRun(
        run_id=WorkflowRunId.parse(run_id),
        workflow_name="demo",
        workflow_version="1",
        definition_fingerprint="sha256:def",
        plan_fingerprint="sha256:plan",
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse(f"C-{run_id}"),
        ),
        created_at=T0,
    )


def task_run(
    task_run_id: str = "TR-1",
    *,
    workflow_run_id: str = "W-1",
    task_key: str = "fetch",
) -> TaskRun:
    return TaskRun(
        task_run_id=TaskRunId.parse(task_run_id),
        workflow_run_id=WorkflowRunId.parse(workflow_run_id),
        task_key=task_key,
        created_at=T0,
    )


def attempt(
    attempt_id: str,
    *,
    task_run_id: str = "TR-1",
    attempt_number: int,
) -> TaskAttempt:
    return TaskAttempt(
        attempt_id=TaskAttemptId.parse(attempt_id),
        task_run_id=TaskRunId.parse(task_run_id),
        attempt_number=attempt_number,
        created_at=T0,
    )


class MetadataStoreContractSuite:
    """Behavior reusable by memory, SQLite and PostgreSQL implementations."""

    store: MetadataStore

    def test_store_satisfies_runtime_checkable_protocol(self) -> None:
        assert isinstance(self.store, MetadataStore)

    def test_workflow_run_roundtrip_is_defensive_copy(self) -> None:
        original = workflow_run()
        self.store.create_workflow_run(original)

        loaded = self.store.get_workflow_run(original.run_id)
        assert loaded.run_id == original.run_id
        assert loaded.status is WorkflowRunStatus.PENDING
        assert loaded is not original

        WorkflowRunStateMachine().transition(
            loaded,
            WorkflowRunStatus.RUNNING,
            at=T1,
        )

        persisted = self.store.get_workflow_run(original.run_id)
        assert persisted.status is WorkflowRunStatus.PENDING

    def test_duplicate_workflow_identity_is_rejected(self) -> None:
        run = workflow_run()
        self.store.create_workflow_run(run)

        with pytest.raises(DuplicateMetadataError):
            self.store.create_workflow_run(run)

    def test_conditional_workflow_update_rejects_stale_expected_status(self) -> None:
        run = workflow_run()
        self.store.create_workflow_run(run)

        first = self.store.get_workflow_run(run.run_id)
        WorkflowRunStateMachine().transition(
            first,
            WorkflowRunStatus.RUNNING,
            at=T1,
        )
        self.store.update_workflow_run(
            first,
            expected_status=WorkflowRunStatus.PENDING,
            transitioned_at=T1,
        )

        stale = workflow_run()
        WorkflowRunStateMachine().transition(
            stale,
            WorkflowRunStatus.CANCELLATION_REQUESTED,
            at=T2,
        )
        with pytest.raises(MetadataConflictError):
            self.store.update_workflow_run(
                stale,
                expected_status=WorkflowRunStatus.PENDING,
                transitioned_at=T2,
            )

    def test_identity_overwrite_is_rejected(self) -> None:
        run = workflow_run()
        self.store.create_workflow_run(run)

        changed = self.store.get_workflow_run(run.run_id)
        changed.workflow_name = "other"

        with pytest.raises(MetadataInvariantError):
            self.store.update_workflow_run(
                changed,
                expected_status=WorkflowRunStatus.PENDING,
            )

    def test_state_history_records_creation_and_transitions(self) -> None:
        run = workflow_run()
        self.store.create_workflow_run(run)

        loaded = self.store.get_workflow_run(run.run_id)
        WorkflowRunStateMachine().transition(
            loaded,
            WorkflowRunStatus.RUNNING,
            at=T1,
        )
        self.store.update_workflow_run(
            loaded,
            expected_status=WorkflowRunStatus.PENDING,
            transitioned_at=T1,
        )

        history = self.store.list_state_transitions(
            entity_type=StateEntityType.WORKFLOW_RUN,
            entity_id=str(run.run_id),
        )

        assert tuple(record.sequence for record in history) == (1, 2)
        assert history[0].from_status is None
        assert history[0].to_status == WorkflowRunStatus.PENDING.value
        assert history[1].from_status == WorkflowRunStatus.PENDING.value
        assert history[1].to_status == WorkflowRunStatus.RUNNING.value
        assert history[1].occurred_at == T1

    def test_task_run_requires_existing_workflow(self) -> None:
        with pytest.raises(MetadataNotFoundError):
            self.store.create_task_run(task_run())

    def test_task_run_conditional_update_and_history(self) -> None:
        run = workflow_run()
        task = task_run()
        self.store.create_workflow_run(run)
        self.store.create_task_run(task)

        loaded = self.store.get_task_run(task.task_run_id)
        TaskRunStateMachine().transition(loaded, TaskRunStatus.READY, at=T1)
        self.store.update_task_run(
            loaded,
            expected_status=TaskRunStatus.PENDING,
            transitioned_at=T1,
        )

        assert self.store.get_task_run(task.task_run_id).status is TaskRunStatus.READY
        history = self.store.list_state_transitions(
            entity_type=StateEntityType.TASK_RUN,
            entity_id=str(task.task_run_id),
        )
        assert tuple(record.to_status for record in history) == ("PENDING", "READY")

    def test_attempt_history_is_contiguous_and_ordered(self) -> None:
        run = workflow_run()
        task = task_run()
        self.store.create_workflow_run(run)
        self.store.create_task_run(task)

        first = attempt("TA-1", attempt_number=1)
        second = attempt("TA-2", attempt_number=2)
        self.store.append_task_attempt(first)
        self.store.append_task_attempt(second)

        attempts = self.store.list_task_attempts(task.task_run_id)
        assert tuple(value.attempt_number for value in attempts) == (1, 2)
        assert tuple(str(value.attempt_id) for value in attempts) == ("TA-1", "TA-2")

    def test_attempt_history_rejects_gap(self) -> None:
        run = workflow_run()
        task = task_run()
        self.store.create_workflow_run(run)
        self.store.create_task_run(task)

        with pytest.raises(MetadataInvariantError, match="attempt_number 1"):
            self.store.append_task_attempt(attempt("TA-2", attempt_number=2))

    def test_attempt_state_update_is_conditional(self) -> None:
        run = workflow_run()
        task = task_run()
        first = attempt("TA-1", attempt_number=1)
        self.store.create_workflow_run(run)
        self.store.create_task_run(task)
        self.store.append_task_attempt(first)

        loaded = self.store.get_task_attempt(first.attempt_id)
        TaskAttemptStateMachine().transition(
            loaded,
            TaskAttemptStatus.STARTING,
            at=T1,
        )
        self.store.update_task_attempt(
            loaded,
            expected_status=TaskAttemptStatus.PENDING,
            transitioned_at=T1,
        )

        assert self.store.get_task_attempt(first.attempt_id).status is TaskAttemptStatus.STARTING

    def test_external_run_refs_are_scoped_to_attempt_and_sorted(self) -> None:
        run = workflow_run()
        task = task_run()
        first = attempt("TA-1", attempt_number=1)
        self.store.create_workflow_run(run)
        self.store.create_task_run(task)
        self.store.append_task_attempt(first)

        z_ref = ExternalRunRef(
            provider="z-provider",
            external_run_id="2",
            kind="job",
        )
        a_ref = ExternalRunRef(
            provider="a-provider",
            external_run_id="1",
            kind="job",
        )
        self.store.append_external_run_ref(
            attempt_id=first.attempt_id,
            external_ref=z_ref,
        )
        self.store.append_external_run_ref(
            attempt_id=first.attempt_id,
            external_ref=a_ref,
        )

        refs = self.store.list_external_run_refs(first.attempt_id)
        assert tuple(ref.provider for ref in refs) == ("a-provider", "z-provider")

        with pytest.raises(DuplicateMetadataError):
            self.store.append_external_run_ref(
                attempt_id=first.attempt_id,
                external_ref=a_ref,
            )

    def test_unfinished_workflow_query_excludes_terminal_runs(self) -> None:
        first = workflow_run("W-1")
        second = workflow_run("W-2")
        self.store.create_workflow_run(second)
        self.store.create_workflow_run(first)

        terminal = self.store.get_workflow_run(first.run_id)
        machine = WorkflowRunStateMachine()
        machine.transition(terminal, WorkflowRunStatus.RUNNING, at=T1)
        self.store.update_workflow_run(
            terminal,
            expected_status=WorkflowRunStatus.PENDING,
            transitioned_at=T1,
        )
        machine.transition(terminal, WorkflowRunStatus.SUCCEEDED, at=T2)
        self.store.update_workflow_run(
            terminal,
            expected_status=WorkflowRunStatus.RUNNING,
            transitioned_at=T2,
        )

        unfinished = self.store.list_unfinished_workflow_runs()
        assert tuple(str(run.run_id) for run in unfinished) == ("W-2",)

    def test_runtime_events_are_projected_from_state_transition_truth(self) -> None:
        run = workflow_run()
        task = task_run()
        first = attempt("TA-1", attempt_number=1)
        self.store.create_workflow_run(run)
        self.store.create_task_run(task)
        self.store.append_task_attempt(first)

        loaded_run = self.store.get_workflow_run(run.run_id)
        WorkflowRunStateMachine().transition(
            loaded_run,
            WorkflowRunStatus.RUNNING,
            at=T1,
        )
        self.store.update_workflow_run(
            loaded_run,
            expected_status=WorkflowRunStatus.PENDING,
            transitioned_at=T1,
        )

        events = self.store.list_runtime_events(run.run_id)

        assert len(events) == 1
        assert events[0].event_type is RuntimeEventType.WORKFLOW_STARTED
        assert events[0].event_id == f"{run.run_id}:event-{events[0].sequence}"
        assert events[0].from_status == WorkflowRunStatus.PENDING.value
        assert events[0].to_status == WorkflowRunStatus.RUNNING.value
        assert events[0].workflow_run_id == run.run_id

    def test_output_checkpoint_is_portable_immutable_and_idempotent(self) -> None:
        run = workflow_run()
        task = task_run()
        self.store.create_workflow_run(run)
        self.store.create_task_run(task)

        persisted_task = self.store.get_task_run(task.task_run_id)
        machine = TaskRunStateMachine()
        machine.transition(persisted_task, TaskRunStatus.READY, at=T1)
        self.store.update_task_run(
            persisted_task,
            expected_status=TaskRunStatus.PENDING,
            transitioned_at=T1,
        )
        machine.transition(persisted_task, TaskRunStatus.RUNNING, at=T2)
        self.store.update_task_run(
            persisted_task,
            expected_status=TaskRunStatus.READY,
            transitioned_at=T2,
        )
        machine.transition(persisted_task, TaskRunStatus.SUCCEEDED, at=T3)
        self.store.update_task_run(
            persisted_task,
            expected_status=TaskRunStatus.RUNNING,
            transitioned_at=T3,
        )

        checkpoint = TaskOutputCheckpoint(
            task_run_id=task.task_run_id,
            output={"rows": 3, "nested": ["a", True]},
            recorded_at=T3,
        )
        self.store.set_task_output_checkpoint(checkpoint)
        self.store.set_task_output_checkpoint(checkpoint)

        loaded = self.store.get_task_output_checkpoint(task.task_run_id)
        assert loaded == checkpoint
        assert loaded.digest.startswith("sha256:")

        with pytest.raises(MetadataConflictError):
            self.store.set_task_output_checkpoint(
                TaskOutputCheckpoint(
                    task_run_id=task.task_run_id,
                    output={"rows": 4},
                    recorded_at=T3,
                )
            )

    def test_output_checkpoint_requires_successful_task(self) -> None:
        run = workflow_run()
        task = task_run()
        self.store.create_workflow_run(run)
        self.store.create_task_run(task)

        with pytest.raises(MetadataInvariantError, match="SUCCEEDED"):
            self.store.set_task_output_checkpoint(
                TaskOutputCheckpoint(
                    task_run_id=task.task_run_id,
                    output={"rows": 1},
                    recorded_at=T1,
                )
            )

    def test_manifest_reference_hook_is_idempotent_but_not_last_write_wins(self) -> None:
        run = workflow_run()
        self.store.create_workflow_run(run)

        reference = ManifestReference(
            locator="memory://manifest/W-1",
            schema_version="1",
            digest="sha256:manifest",
        )
        self.store.set_manifest_reference(run.run_id, reference)
        self.store.set_manifest_reference(run.run_id, reference)
        assert self.store.get_manifest_reference(run.run_id) == reference

        with pytest.raises(MetadataConflictError):
            self.store.set_manifest_reference(
                run.run_id,
                ManifestReference(
                    locator="memory://manifest/other",
                    schema_version="1",
                ),
            )
