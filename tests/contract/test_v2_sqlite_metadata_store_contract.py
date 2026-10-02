"""Apply the reusable V2 MetadataStore contract to durable SQLite."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyworkflowkit.diagnostics import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.migrations import MIGRATION_HEAD_REVISION
from pyworkflowkit.persistence import ManifestReference, SQLiteMetadataStore
from pyworkflowkit.runtime import ExternalRunRef
from pyworkflowkit.states import (
    TaskAttemptStateMachine,
    TaskAttemptStatus,
    TaskRunStateMachine,
    TaskRunStatus,
    WorkflowRunStateMachine,
    WorkflowRunStatus,
)

from .v2_metadata_store_conformance import (
    T1,
    T2,
    T3,
    MetadataStoreContractSuite,
    attempt,
    task_run,
    workflow_run,
)


class TestSQLiteMetadataStoreContract(MetadataStoreContractSuite):
    store: SQLiteMetadataStore

    @pytest.fixture(autouse=True)
    def _sqlite_store(self, tmp_path: Path):
        self.store = SQLiteMetadataStore(tmp_path / "contract.sqlite3", wal=False)
        yield
        self.store.close()

    def test_store_reports_durable_schema_identity(self) -> None:
        metadata = self.store.metadata()

        assert metadata.durable is True
        assert metadata.schema_version == MIGRATION_HEAD_REVISION
        assert metadata.supports_concurrent_writers is True
        assert metadata.supports_atomic_batch is False


def test_sqlite_restart_preserves_v2_runtime_and_reconciliation_evidence(
    tmp_path: Path,
) -> None:
    database = tmp_path / "restart.sqlite3"
    run = workflow_run()
    task = task_run()
    first = attempt("TA-1", attempt_number=1)
    external_ref = ExternalRunRef(
        provider="remote-provider",
        external_run_id="REMOTE-42",
        kind="job",
        status_hint="unknown",
        status_locator="https://provider.invalid/runs/REMOTE-42",
        correlation_id=run.correlation.correlation_id,
        causation_id="submission-42",
        metadata=(("region", "eu-west"), ("owner", "lot10")),
    )
    failure = FailureEvidence(
        error_code="REMOTE-UNKNOWN",
        category=FailureCategory.UNKNOWN_OUTCOME,
        retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
        uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
        correlation_id=run.correlation.correlation_id,
        workflow_run_id=str(run.run_id),
        task_run_id=str(task.task_run_id),
        task_attempt_id=str(first.attempt_id),
        external_run=external_ref,
        source_component="lot10-test",
        provider_code="REMOTE-202",
        message_summary="remote outcome not confirmed",
        details=(("phase", "submit"),),
    )

    with SQLiteMetadataStore(database, wal=False) as store:
        store.create_workflow_run(run)
        store.create_task_run(task)
        store.append_task_attempt(first)

        persisted_run = store.get_workflow_run(run.run_id)
        WorkflowRunStateMachine().transition(
            persisted_run,
            WorkflowRunStatus.RUNNING,
            at=T1,
        )
        store.update_workflow_run(
            persisted_run,
            expected_status=WorkflowRunStatus.PENDING,
            transitioned_at=T1,
        )

        persisted_task = store.get_task_run(task.task_run_id)
        TaskRunStateMachine().transition(
            persisted_task,
            TaskRunStatus.READY,
            at=T1,
        )
        store.update_task_run(
            persisted_task,
            expected_status=TaskRunStatus.PENDING,
            transitioned_at=T1,
        )
        TaskRunStateMachine().transition(
            persisted_task,
            TaskRunStatus.RUNNING,
            at=T2,
        )
        store.update_task_run(
            persisted_task,
            expected_status=TaskRunStatus.READY,
            transitioned_at=T2,
        )

        persisted_attempt = store.get_task_attempt(first.attempt_id)
        TaskAttemptStateMachine().transition(
            persisted_attempt,
            TaskAttemptStatus.STARTING,
            at=T1,
        )
        store.update_task_attempt(
            persisted_attempt,
            expected_status=TaskAttemptStatus.PENDING,
            transitioned_at=T1,
        )
        TaskAttemptStateMachine().transition(
            persisted_attempt,
            TaskAttemptStatus.RUNNING,
            at=T2,
        )
        store.update_task_attempt(
            persisted_attempt,
            expected_status=TaskAttemptStatus.STARTING,
            transitioned_at=T2,
        )

        store.append_external_run_ref(
            attempt_id=first.attempt_id,
            external_ref=external_ref,
        )

        TaskAttemptStateMachine().transition(
            persisted_attempt,
            TaskAttemptStatus.REQUIRES_RECONCILIATION,
            at=T3,
            failure=failure,
        )
        store.update_task_attempt(
            persisted_attempt,
            expected_status=TaskAttemptStatus.RUNNING,
            transitioned_at=T3,
        )
        TaskRunStateMachine().transition(
            persisted_task,
            TaskRunStatus.UNKNOWN_OUTCOME,
            at=T3,
            failure=failure,
        )
        store.update_task_run(
            persisted_task,
            expected_status=TaskRunStatus.RUNNING,
            transitioned_at=T3,
        )
        WorkflowRunStateMachine().transition(
            persisted_run,
            WorkflowRunStatus.UNKNOWN_OUTCOME,
            at=T3,
            failure=failure,
        )
        store.update_workflow_run(
            persisted_run,
            expected_status=WorkflowRunStatus.RUNNING,
            transitioned_at=T3,
        )

        store.set_manifest_reference(
            run.run_id,
            ManifestReference(
                locator="file:///tmp/manifest.json",
                schema_version="1",
                digest="sha256:lot10",
            ),
        )

    with SQLiteMetadataStore(database, wal=False) as reopened:
        loaded_run = reopened.get_workflow_run(run.run_id)
        loaded_task = reopened.get_task_run(task.task_run_id)
        loaded_attempt = reopened.get_task_attempt(first.attempt_id)
        refs = reopened.list_external_run_refs(first.attempt_id)
        transitions = reopened.list_state_transitions()

        assert loaded_run.status is WorkflowRunStatus.UNKNOWN_OUTCOME
        assert loaded_task.status is TaskRunStatus.UNKNOWN_OUTCOME
        assert loaded_attempt.status is TaskAttemptStatus.REQUIRES_RECONCILIATION
        assert loaded_run.failure == failure
        assert loaded_task.failure == failure
        assert loaded_attempt.failure == failure
        assert refs == (external_ref,)
        assert reopened.get_manifest_reference(run.run_id) == ManifestReference(
            locator="file:///tmp/manifest.json",
            schema_version="1",
            digest="sha256:lot10",
        )
        assert tuple(record.sequence for record in transitions) == tuple(
            range(1, len(transitions) + 1)
        )
        assert len(transitions) == 11
