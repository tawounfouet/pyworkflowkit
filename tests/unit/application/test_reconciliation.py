"""Tests for M38 external reconciliation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast
from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.application.reconciliation import (
    ExternalRunVerifierRegistry,
    ReconciliationDisposition,
    ReconciliationService,
)
from pyworkflowkit.domain.enums import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus
from pyworkflowkit.domain.ids import (
    ExternalRunRefId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import ExternalRunRef
from pyworkflowkit.errors import (
    DuplicateReconciliationVerifierError,
    ReconciliationError,
)
from pyworkflowkit.ports.reconciliation import ExternalRunStatus, ExternalRunVerifier

NOW = datetime(2026, 9, 27, 14, 0, tzinfo=UTC)
OLD = NOW - timedelta(hours=2)


class FixedClock:
    def now(self) -> datetime:
        return NOW


@dataclass
class StaticVerifier:
    provider: str
    statuses: dict[str, ExternalRunStatus]

    def verify(self, external_ref: ExternalRunRef) -> ExternalRunStatus:
        return self.statuses[external_ref.external_run_id]


@dataclass
class RaisingVerifier:
    provider: str

    def verify(self, external_ref: ExternalRunRef) -> ExternalRunStatus:
        del external_ref
        raise RuntimeError("provider secret detail")


@dataclass
class InvalidVerifier:
    provider: str

    def verify(self, external_ref: ExternalRunRef) -> str:
        del external_ref
        return "succeeded"


def _service(
    store: MemoryMetadataStore,
    *verifiers: StaticVerifier | RaisingVerifier,
) -> ReconciliationService:
    registry = ExternalRunVerifierRegistry()
    for verifier in verifiers:
        registry.register(verifier)
    return ReconciliationService(
        metadata_store=store,
        clock=FixedClock(),
        verifier_registry=registry,
        stale_after=timedelta(minutes=5),
    )


def _persist(
    store: MemoryMetadataStore,
    *,
    task_status: TaskRunStatus = TaskRunStatus.RUNNING,
    attempt_status: TaskAttemptStatus | None = TaskAttemptStatus.RUNNING,
    refs: tuple[tuple[str, str], ...] = (("remote", "ext-1"),),
    timestamp: datetime = OLD,
) -> tuple[WorkflowRunId, TaskRunId]:
    run_id = WorkflowRunId("run")
    task_run_id = TaskRunId("task-run")

    with store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=run_id,
                workflow_id=WorkflowId("workflow"),
                workflow_version="1",
                status=WorkflowRunStatus.RUNNING,
                created_at=timestamp,
                started_at=timestamp,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=task_run_id,
                run_id=run_id,
                task_id=TaskId("task"),
                status=task_status,
                created_at=timestamp,
                started_at=timestamp if task_status is TaskRunStatus.RUNNING else None,
            )
        )
        if attempt_status is not None:
            uow.add_task_attempt(
                TaskAttempt(
                    attempt_id=TaskAttemptId("attempt-1"),
                    task_run_id=task_run_id,
                    attempt_number=1,
                    status=attempt_status,
                    started_at=timestamp,
                    finished_at=(
                        timestamp + timedelta(seconds=1)
                        if attempt_status is not TaskAttemptStatus.RUNNING
                        else None
                    ),
                )
            )
        for index, (provider, external_run_id) in enumerate(refs, start=1):
            uow.add_external_run_ref(
                task_run_id=task_run_id,
                external_ref=ExternalRunRef(
                    external_ref_id=ExternalRunRefId(f"external-{index}"),
                    provider=provider,
                    external_run_id=external_run_id,
                ),
            )
        uow.commit()

    return run_id, task_run_id


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ExternalRunStatus.SUCCEEDED, ReconciliationDisposition.CONFIRMED_SUCCEEDED),
        (ExternalRunStatus.FAILED, ReconciliationDisposition.CONFIRMED_FAILED),
        (ExternalRunStatus.CANCELLED, ReconciliationDisposition.CONFIRMED_CANCELLED),
        (ExternalRunStatus.RUNNING, ReconciliationDisposition.STILL_RUNNING),
    ],
)
def test_external_status_is_normalized_to_task_disposition(
    status: ExternalRunStatus,
    expected: ReconciliationDisposition,
) -> None:
    store = MemoryMetadataStore()
    run_id, task_run_id = _persist(store)
    service = _service(store, StaticVerifier("remote", {"ext-1": status}))

    report = service.reconcile(run_id)

    assert len(report.task_reconciliations) == 1
    item = report.task_reconciliations[0]
    assert item.task_run_id == str(task_run_id)
    assert item.disposition is expected
    assert item.observations[0].status is status
    assert store.get_workflow_run(run_id).status is WorkflowRunStatus.RUNNING
    assert store.get_task_run(task_run_id).status is TaskRunStatus.RUNNING


@pytest.mark.parametrize(
    "status",
    [ExternalRunStatus.UNKNOWN, ExternalRunStatus.NOT_FOUND],
)
def test_inconclusive_external_status_requires_manual_action(
    status: ExternalRunStatus,
) -> None:
    store = MemoryMetadataStore()
    run_id, _ = _persist(store)
    service = _service(store, StaticVerifier("remote", {"ext-1": status}))

    report = service.reconcile(run_id)

    item = report.task_reconciliations[0]
    assert item.disposition is ReconciliationDisposition.MANUAL_REQUIRED
    assert item.reasons == ("external_status_is_not_conclusive",)
    assert report.requires_manual_action is True


def test_missing_verifier_becomes_unknown_evidence_not_exception() -> None:
    store = MemoryMetadataStore()
    run_id, _ = _persist(store)

    report = _service(store).reconcile(run_id)

    observation = report.task_reconciliations[0].observations[0]
    assert observation.status is ExternalRunStatus.UNKNOWN
    assert observation.reason == "verifier_not_registered"
    assert report.requires_manual_action is True


def test_verifier_failure_is_isolated_without_copying_error_message() -> None:
    store = MemoryMetadataStore()
    run_id, _ = _persist(store)

    report = _service(store, RaisingVerifier("remote")).reconcile(run_id)

    observation = report.task_reconciliations[0].observations[0]
    assert observation.status is ExternalRunStatus.UNKNOWN
    assert observation.reason == "verification_failed:RuntimeError"
    assert "secret" not in observation.reason


def test_invalid_verifier_status_is_treated_as_unknown() -> None:
    store = MemoryMetadataStore()
    run_id, _ = _persist(store)
    registry = ExternalRunVerifierRegistry()
    registry.register(cast(ExternalRunVerifier, InvalidVerifier("remote")))

    report = ReconciliationService(
        metadata_store=store,
        clock=FixedClock(),
        verifier_registry=registry,
        stale_after=timedelta(minutes=5),
    ).reconcile(run_id)

    observation = report.task_reconciliations[0].observations[0]
    assert observation.status is ExternalRunStatus.UNKNOWN
    assert observation.reason == "verifier_returned_invalid_status"


def test_conflicting_external_statuses_require_manual_action() -> None:
    store = MemoryMetadataStore()
    run_id, _ = _persist(
        store,
        refs=(("remote", "ext-1"), ("remote", "ext-2")),
    )
    service = _service(
        store,
        StaticVerifier(
            "remote",
            {
                "ext-1": ExternalRunStatus.SUCCEEDED,
                "ext-2": ExternalRunStatus.FAILED,
            },
        ),
    )

    report = service.reconcile(run_id)

    item = report.task_reconciliations[0]
    assert item.disposition is ReconciliationDisposition.MANUAL_REQUIRED
    assert item.reasons == ("conflicting_external_statuses",)


def test_running_local_work_without_external_reference_requires_manual_action() -> None:
    store = MemoryMetadataStore()
    run_id, _ = _persist(store, refs=())

    report = _service(store).reconcile(run_id)

    item = report.task_reconciliations[0]
    assert item.disposition is ReconciliationDisposition.MANUAL_REQUIRED
    assert item.observations == ()
    assert item.reasons == ("local_running_work_has_no_external_reconciliation_evidence",)


def test_ready_task_without_external_work_needs_no_reconciliation() -> None:
    store = MemoryMetadataStore()
    run_id, _ = _persist(
        store,
        task_status=TaskRunStatus.READY,
        attempt_status=None,
        refs=(),
    )

    report = _service(store).reconcile(run_id)

    assert report.task_reconciliations == ()
    assert report.fully_resolved is True
    assert report.requires_manual_action is False


def test_still_running_external_work_is_not_fully_resolved() -> None:
    store = MemoryMetadataStore()
    run_id, _ = _persist(store)
    service = _service(
        store,
        StaticVerifier("remote", {"ext-1": ExternalRunStatus.RUNNING}),
    )

    report = service.reconcile(run_id)

    assert report.has_still_running is True
    assert report.fully_resolved is False


def test_reconciliation_rejects_non_stale_run() -> None:
    store = MemoryMetadataStore()
    run_id, _ = _persist(store, timestamp=NOW)

    with pytest.raises(ReconciliationError, match="not stale_candidate"):
        _service(
            store,
            StaticVerifier("remote", {"ext-1": ExternalRunStatus.RUNNING}),
        ).reconcile(run_id)


def test_verifier_registry_rejects_duplicate_provider() -> None:
    registry = ExternalRunVerifierRegistry()
    registry.register(StaticVerifier("remote", {"ext-1": ExternalRunStatus.RUNNING}))
    assert registry.providers == ("remote",)

    with pytest.raises(DuplicateReconciliationVerifierError):
        registry.register(StaticVerifier("remote", {"ext-1": ExternalRunStatus.SUCCEEDED}))


def test_verifier_registry_rejects_blank_provider() -> None:
    registry = ExternalRunVerifierRegistry()

    with pytest.raises(ValueError, match="non-empty"):
        registry.register(StaticVerifier(" ", {}))
