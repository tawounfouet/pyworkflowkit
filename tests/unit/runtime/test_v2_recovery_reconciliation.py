"""LOT-11 unit tests for V2 recovery inspection and reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit.diagnostics import (
    RecoveryDisposition,
    RecoveryInspector,
)
from pyworkflowkit.errors import DuplicateReconciliationVerifierError
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    ExternalRunRef,
    ExternalRunStatus,
    ExternalRunVerifierRegistry,
    ReconciliationDisposition,
    ReconciliationService,
    TaskAttempt,
    TaskAttemptId,
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

T0 = datetime(2026, 10, 3, 8, 0, tzinfo=UTC)
T1 = T0 + timedelta(seconds=1)
T2 = T0 + timedelta(seconds=2)
T3 = T0 + timedelta(seconds=3)
T4 = T0 + timedelta(seconds=4)


class FixedClock:
    def now(self) -> datetime:
        return T4


@dataclass
class StaticVerifier:
    provider: str
    status: ExternalRunStatus

    def verify(self, external_ref: ExternalRunRef) -> ExternalRunStatus:
        del external_ref
        return self.status


@dataclass
class RaisingVerifier:
    provider: str

    def verify(self, external_ref: ExternalRunRef) -> ExternalRunStatus:
        del external_ref
        raise RuntimeError("provider secret detail")


def _persist_ambiguous(
    store: InMemoryMetadataStore,
    *,
    with_ref: bool = True,
    second_pending_task: bool = False,
) -> tuple[WorkflowRunId, TaskRunId, TaskAttemptId]:
    run = WorkflowRun(
        run_id=WorkflowRunId.parse("W-1"),
        workflow_name="demo",
        workflow_version="1",
        definition_fingerprint="sha256:def",
        plan_fingerprint="sha256:plan",
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-1"),
        ),
        created_at=T0,
    )
    task = TaskRun(
        task_run_id=TaskRunId.parse("TR-1"),
        workflow_run_id=run.run_id,
        task_key="remote",
        created_at=T0,
    )
    attempt = TaskAttempt(
        attempt_id=TaskAttemptId.parse("TA-1"),
        task_run_id=task.task_run_id,
        attempt_number=1,
        created_at=T0,
    )
    store.create_workflow_run(run)
    store.create_task_run(task)
    store.append_task_attempt(attempt)

    workflow_states = WorkflowRunStateMachine()
    task_states = TaskRunStateMachine()
    attempt_states = TaskAttemptStateMachine()

    workflow_states.transition(run, WorkflowRunStatus.RUNNING, at=T1)
    store.update_workflow_run(
        run,
        expected_status=WorkflowRunStatus.PENDING,
        transitioned_at=T1,
    )
    task_states.transition(task, TaskRunStatus.READY, at=T1)
    store.update_task_run(
        task,
        expected_status=TaskRunStatus.PENDING,
        transitioned_at=T1,
    )
    task_states.transition(task, TaskRunStatus.RUNNING, at=T2)
    store.update_task_run(
        task,
        expected_status=TaskRunStatus.READY,
        transitioned_at=T2,
    )
    attempt_states.transition(attempt, TaskAttemptStatus.STARTING, at=T1)
    store.update_task_attempt(
        attempt,
        expected_status=TaskAttemptStatus.PENDING,
        transitioned_at=T1,
    )
    attempt_states.transition(attempt, TaskAttemptStatus.RUNNING, at=T2)
    store.update_task_attempt(
        attempt,
        expected_status=TaskAttemptStatus.STARTING,
        transitioned_at=T2,
    )
    attempt_states.transition(
        attempt,
        TaskAttemptStatus.REQUIRES_RECONCILIATION,
        at=T3,
    )
    store.update_task_attempt(
        attempt,
        expected_status=TaskAttemptStatus.RUNNING,
        transitioned_at=T3,
    )
    task_states.transition(task, TaskRunStatus.UNKNOWN_OUTCOME, at=T3)
    store.update_task_run(
        task,
        expected_status=TaskRunStatus.RUNNING,
        transitioned_at=T3,
    )
    workflow_states.transition(run, WorkflowRunStatus.UNKNOWN_OUTCOME, at=T3)
    store.update_workflow_run(
        run,
        expected_status=WorkflowRunStatus.RUNNING,
        transitioned_at=T3,
    )

    if with_ref:
        store.append_external_run_ref(
            attempt_id=attempt.attempt_id,
            external_ref=ExternalRunRef(
                provider="remote",
                external_run_id="EXT-1",
                kind="job",
                correlation_id=run.correlation.correlation_id,
            ),
        )

    if second_pending_task:
        store.create_task_run(
            TaskRun(
                task_run_id=TaskRunId.parse("TR-2"),
                workflow_run_id=run.run_id,
                task_key="downstream",
                created_at=T0,
            )
        )

    return run.run_id, task.task_run_id, attempt.attempt_id


def _service(
    store: InMemoryMetadataStore,
    *verifiers: StaticVerifier | RaisingVerifier,
) -> ReconciliationService:
    registry = ExternalRunVerifierRegistry()
    for verifier in verifiers:
        registry.register(verifier)
    return ReconciliationService(
        metadata=store,
        verifier_registry=registry,
        clock=FixedClock(),
    )


def test_recovery_inspector_classifies_external_unknown_outcome() -> None:
    store = InMemoryMetadataStore()
    run_id, task_run_id, attempt_id = _persist_ambiguous(store)

    assessment = RecoveryInspector(metadata=store).assess(run_id)

    assert assessment.disposition is RecoveryDisposition.REQUIRES_RECONCILIATION
    assert assessment.requires_reconciliation is True
    assert assessment.task_assessments[0].task_run_id == task_run_id
    assert assessment.task_assessments[0].latest_attempt_id == attempt_id
    assert assessment.task_assessments[0].external_run_ref_count == 1


def test_recovery_inspector_requires_manual_action_without_external_evidence() -> None:
    store = InMemoryMetadataStore()
    run_id, _, _ = _persist_ambiguous(store, with_ref=False)

    assessment = RecoveryInspector(metadata=store).assess(run_id)

    assert assessment.disposition is RecoveryDisposition.MANUAL_REQUIRED
    assert assessment.requires_manual_action is True


def test_recovery_discovery_returns_nonterminal_runs() -> None:
    store = InMemoryMetadataStore()
    run_id, _, _ = _persist_ambiguous(store)

    discovered = RecoveryInspector(metadata=store).discover()

    assert tuple(item.workflow_run_id for item in discovered) == (run_id,)


@pytest.mark.parametrize(
    ("external_status", "attempt_status", "task_status", "workflow_status", "disposition"),
    [
        (
            ExternalRunStatus.SUCCEEDED,
            TaskAttemptStatus.SUCCEEDED,
            TaskRunStatus.SUCCEEDED,
            WorkflowRunStatus.SUCCEEDED,
            ReconciliationDisposition.RESOLVED_SUCCEEDED,
        ),
        (
            ExternalRunStatus.FAILED,
            TaskAttemptStatus.FAILED,
            TaskRunStatus.FAILED,
            WorkflowRunStatus.FAILED,
            ReconciliationDisposition.RESOLVED_FAILED,
        ),
        (
            ExternalRunStatus.CANCELLED,
            TaskAttemptStatus.CANCELLED,
            TaskRunStatus.CANCELLED,
            WorkflowRunStatus.CANCELLED,
            ReconciliationDisposition.RESOLVED_CANCELLED,
        ),
    ],
)
def test_external_truth_is_applied_to_same_attempt_without_blind_retry(
    external_status: ExternalRunStatus,
    attempt_status: TaskAttemptStatus,
    task_status: TaskRunStatus,
    workflow_status: WorkflowRunStatus,
    disposition: ReconciliationDisposition,
) -> None:
    store = InMemoryMetadataStore()
    run_id, task_run_id, attempt_id = _persist_ambiguous(store)
    service = _service(store, StaticVerifier("remote", external_status))

    report = service.reconcile(run_id)

    assert report.task_reconciliations[0].disposition is disposition
    assert store.get_task_attempt(attempt_id).status is attempt_status
    assert store.get_task_run(task_run_id).status is task_status
    assert store.get_workflow_run(run_id).status is workflow_status
    assert len(store.list_task_attempts(task_run_id)) == 1


def test_external_work_still_running_does_not_mutate_uncertain_state() -> None:
    store = InMemoryMetadataStore()
    run_id, task_run_id, attempt_id = _persist_ambiguous(store)

    report = _service(
        store,
        StaticVerifier("remote", ExternalRunStatus.RUNNING),
    ).reconcile(run_id)

    assert report.has_still_running is True
    assert report.fully_resolved is False
    assert store.get_task_attempt(attempt_id).status is TaskAttemptStatus.REQUIRES_RECONCILIATION
    assert store.get_task_run(task_run_id).status is TaskRunStatus.UNKNOWN_OUTCOME
    assert store.get_workflow_run(run_id).status is WorkflowRunStatus.UNKNOWN_OUTCOME


def test_missing_verifier_requires_manual_action_without_state_invention() -> None:
    store = InMemoryMetadataStore()
    run_id, task_run_id, attempt_id = _persist_ambiguous(store)

    report = _service(store).reconcile(run_id)

    item = report.task_reconciliations[0]
    assert item.disposition is ReconciliationDisposition.MANUAL_REQUIRED
    assert item.observations[0].reason == "verifier_not_registered"
    assert store.get_task_attempt(attempt_id).status is TaskAttemptStatus.REQUIRES_RECONCILIATION
    assert store.get_task_run(task_run_id).status is TaskRunStatus.UNKNOWN_OUTCOME


def test_verifier_exception_is_redacted_to_exception_type() -> None:
    store = InMemoryMetadataStore()
    run_id, _, _ = _persist_ambiguous(store)

    report = _service(store, RaisingVerifier("remote")).reconcile(run_id)

    reason = report.task_reconciliations[0].observations[0].reason
    assert reason == "verification_failed:RuntimeError"
    assert "secret" not in reason


def test_reconciled_success_returns_workflow_to_running_when_downstream_is_pending() -> None:
    store = InMemoryMetadataStore()
    run_id, _, _ = _persist_ambiguous(store, second_pending_task=True)

    report = _service(
        store,
        StaticVerifier("remote", ExternalRunStatus.SUCCEEDED),
    ).reconcile(run_id)

    assert report.workflow_status_after is WorkflowRunStatus.RUNNING
    assert store.get_workflow_run(run_id).status is WorkflowRunStatus.RUNNING


def test_terminal_attempt_repairs_task_and_workflow_without_provider_call() -> None:
    store = InMemoryMetadataStore()
    run_id, task_run_id, attempt_id = _persist_ambiguous(store, with_ref=False)

    attempt = store.get_task_attempt(attempt_id)
    TaskAttemptStateMachine().transition(
        attempt,
        TaskAttemptStatus.SUCCEEDED,
        at=T4,
    )
    store.update_task_attempt(
        attempt,
        expected_status=TaskAttemptStatus.REQUIRES_RECONCILIATION,
        transitioned_at=T4,
    )

    report = _service(store).reconcile(run_id)

    disposition = report.task_reconciliations[0].disposition
    assert disposition is ReconciliationDisposition.RESOLVED_SUCCEEDED
    assert store.get_task_run(task_run_id).status is TaskRunStatus.SUCCEEDED
    assert store.get_workflow_run(run_id).status is WorkflowRunStatus.SUCCEEDED


def test_registry_rejects_duplicate_provider() -> None:
    registry = ExternalRunVerifierRegistry()
    registry.register(StaticVerifier("remote", ExternalRunStatus.RUNNING))

    with pytest.raises(DuplicateReconciliationVerifierError):
        registry.register(StaticVerifier("remote", ExternalRunStatus.SUCCEEDED))
