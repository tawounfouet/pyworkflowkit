"""Tests for M39 same-run resume semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.reconciliation import (
    ReconciliationDisposition,
    ReconciliationReport,
    TaskReconciliation,
)
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    RuntimeEventType,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import (
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.errors import MetadataNotFoundError, ResumeError
from pyworkflowkit.ports.executor import RunContext

NOW = datetime(2026, 9, 27, 16, 0, tzinfo=UTC)
OLD = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
RUN_ID = WorkflowRunId("resume-run")


class FixedClock:
    def now(self) -> datetime:
        return NOW


class NoopSleeper:
    def sleep(self, seconds: float) -> None:
        del seconds


class DeterministicIdFactory:
    def new_workflow_run_id(self) -> WorkflowRunId:
        return WorkflowRunId("unexpected-new-run")

    def new_task_run_id(
        self,
        *,
        run_id: WorkflowRunId,
        task_id: TaskId,
    ) -> TaskRunId:
        return TaskRunId(f"{run_id}:{task_id}")

    def new_task_attempt_id(
        self,
        *,
        task_run_id: TaskRunId,
        attempt_number: int,
    ) -> TaskAttemptId:
        return TaskAttemptId(f"{task_run_id}:attempt-{attempt_number}")

    def new_runtime_event_id(
        self,
        *,
        run_id: WorkflowRunId,
        event_sequence: int,
    ) -> RuntimeEventId:
        return RuntimeEventId(f"{run_id}:event-{event_sequence}")


def _workflow(*tasks: TaskDefinition) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("workflow"),
        version="1",
        tasks=tasks,
    )


def _task(task_id: str, *depends_on: str) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(task_id),
        handler_ref=f"handlers:{task_id}",
        depends_on=tuple(TaskId(value) for value in depends_on),
    )


def _runner(
    store: MemoryMetadataStore,
    handlers: dict[str, object],
) -> Runner:
    registry = HandlerRegistry()
    for handler_ref, handler in handlers.items():
        registry.register(handler_ref, handler)  # type: ignore[arg-type]
    return Runner(
        metadata_store=store,
        handler_registry=registry,
        executor=LocalExecutor(),
        clock=FixedClock(),
        id_factory=DeterministicIdFactory(),
        sleeper=NoopSleeper(),
    )


def _empty_report() -> ReconciliationReport:
    return ReconciliationReport(run_id=str(RUN_ID), task_reconciliations=())


def _persist_completed_a_pending_b(
    store: MemoryMetadataStore,
    *,
    checkpoint: object = 7,
    persist_checkpoint: bool = True,
    b_status: TaskRunStatus = TaskRunStatus.PENDING,
) -> tuple[TaskRunId, TaskRunId]:
    a_run_id = TaskRunId("resume-run:A")
    b_run_id = TaskRunId("resume-run:B")
    with store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=RUN_ID,
                workflow_id=WorkflowId("workflow"),
                workflow_version="1",
                status=WorkflowRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=a_run_id,
                run_id=RUN_ID,
                task_id=TaskId("A"),
                status=TaskRunStatus.SUCCEEDED,
                created_at=OLD,
                started_at=OLD,
                finished_at=OLD,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("resume-run:A:attempt-1"),
                task_run_id=a_run_id,
                attempt_number=1,
                status=TaskAttemptStatus.SUCCEEDED,
                started_at=OLD,
                finished_at=OLD,
            )
        )
        if persist_checkpoint:
            uow.add_task_output_checkpoint(task_run_id=a_run_id, output=checkpoint)
        uow.add_task_run(
            TaskRun(
                task_run_id=b_run_id,
                run_id=RUN_ID,
                task_id=TaskId("B"),
                status=b_status,
                created_at=OLD,
                started_at=None,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("resume-run:event-1"),
                event_type=RuntimeEventType.WORKFLOW_STARTED,
                run_id=RUN_ID,
                occurred_at=OLD,
                event_sequence=1,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("resume-run:event-2"),
                event_type=RuntimeEventType.TASK_SUCCEEDED,
                run_id=RUN_ID,
                occurred_at=OLD,
                event_sequence=2,
                task_run_id=a_run_id,
                task_id=TaskId("A"),
                attempt_number=1,
            )
        )
        if b_status is TaskRunStatus.READY:
            uow.add_event(
                RuntimeEvent(
                    event_id=RuntimeEventId("resume-run:event-3"),
                    event_type=RuntimeEventType.TASK_READY,
                    run_id=RUN_ID,
                    occurred_at=OLD,
                    event_sequence=3,
                    task_run_id=b_run_id,
                    task_id=TaskId("B"),
                )
            )
        uow.commit()
    return a_run_id, b_run_id


def _persist_running_a_pending_b(
    store: MemoryMetadataStore,
) -> tuple[TaskRunId, TaskRunId, TaskAttemptId]:
    a_run_id = TaskRunId("resume-run:A")
    b_run_id = TaskRunId("resume-run:B")
    attempt_id = TaskAttemptId("resume-run:A:attempt-1")
    with store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=RUN_ID,
                workflow_id=WorkflowId("workflow"),
                workflow_version="1",
                status=WorkflowRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=a_run_id,
                run_id=RUN_ID,
                task_id=TaskId("A"),
                status=TaskRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=attempt_id,
                task_run_id=a_run_id,
                attempt_number=1,
                status=TaskAttemptStatus.RUNNING,
                started_at=OLD,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=b_run_id,
                run_id=RUN_ID,
                task_id=TaskId("B"),
                status=TaskRunStatus.PENDING,
                created_at=OLD,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("resume-run:event-1"),
                event_type=RuntimeEventType.WORKFLOW_STARTED,
                run_id=RUN_ID,
                occurred_at=OLD,
                event_sequence=1,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("resume-run:event-2"),
                event_type=RuntimeEventType.TASK_STARTED,
                run_id=RUN_ID,
                occurred_at=OLD,
                event_sequence=2,
                task_run_id=a_run_id,
                task_id=TaskId("A"),
                attempt_number=1,
            )
        )
        uow.commit()
    return a_run_id, b_run_id, attempt_id


def _report(
    *,
    task_run_id: TaskRunId,
    attempt_id: TaskAttemptId,
    disposition: ReconciliationDisposition,
) -> ReconciliationReport:
    return ReconciliationReport(
        run_id=str(RUN_ID),
        task_reconciliations=(
            TaskReconciliation(
                task_run_id=str(task_run_id),
                task_id="A",
                disposition=disposition,
                running_attempt_ids=(str(attempt_id),),
                observations=(),
                reasons=("test",),
            ),
        ),
    )


def test_runner_checkpoints_portable_output_on_success() -> None:
    store = MemoryMetadataStore()
    workflow = _workflow(_task("A"))

    run = _runner(store, {"handlers:A": lambda: {"count": 3}}).run(workflow)
    task_run = store.list_task_runs(run.run_id)[0]

    assert store.get_task_output_checkpoint(task_run.task_run_id) == {"count": 3}


def test_runner_allows_nonportable_live_output_but_does_not_checkpoint_it() -> None:
    store = MemoryMetadataStore()
    workflow = _workflow(_task("A"))
    opaque = object()

    run = _runner(store, {"handlers:A": lambda: opaque}).run(workflow)
    task_run = store.list_task_runs(run.run_id)[0]

    assert run.status is WorkflowRunStatus.SUCCEEDED
    with pytest.raises(MetadataNotFoundError):
        store.get_task_output_checkpoint(task_run.task_run_id)


def test_resume_same_run_skips_completed_task_and_restores_dependency_output() -> None:
    store = MemoryMetadataStore()
    a_run_id, b_run_id = _persist_completed_a_pending_b(store)
    calls: list[str] = []
    observed: list[object] = []

    def b_handler(context: RunContext) -> int:
        calls.append("B")
        observed.append(context.dependency_outputs[TaskId("A")])
        return int(context.dependency_outputs[TaskId("A")]) * 2

    workflow = _workflow(_task("A"), _task("B", "A"))
    runner = _runner(store, {"handlers:B": b_handler})

    resumed = runner.resume(
        workflow,
        run_id=RUN_ID,
        reconciliation=_empty_report(),
    )

    assert resumed.run_id == RUN_ID
    assert resumed.status is WorkflowRunStatus.SUCCEEDED
    assert calls == ["B"]
    assert observed == [7]
    assert len(store.list_workflow_runs()) == 1
    assert len(store.list_task_attempts(a_run_id)) == 1
    assert len(store.list_task_attempts(b_run_id)) == 1
    assert store.get_task_output_checkpoint(b_run_id) == 14

    events = store.list_events(RUN_ID)
    assert tuple(event.event_sequence for event in events) == (1, 2, 3, 4, 5, 6)
    assert tuple(event.event_type for event in events[2:]) == (
        RuntimeEventType.TASK_READY,
        RuntimeEventType.TASK_STARTED,
        RuntimeEventType.TASK_SUCCEEDED,
        RuntimeEventType.WORKFLOW_SUCCEEDED,
    )


def test_resume_ready_task_does_not_emit_duplicate_ready_event() -> None:
    store = MemoryMetadataStore()
    _, b_run_id = _persist_completed_a_pending_b(
        store,
        b_status=TaskRunStatus.READY,
    )
    workflow = _workflow(_task("A"), _task("B", "A"))

    resumed = _runner(store, {"handlers:B": lambda context: "done"}).resume(
        workflow,
        run_id=RUN_ID,
        reconciliation=_empty_report(),
    )

    assert resumed.status is WorkflowRunStatus.SUCCEEDED
    assert len(store.list_task_attempts(b_run_id)) == 1
    ready_events = tuple(
        event
        for event in store.list_events(RUN_ID)
        if event.event_type is RuntimeEventType.TASK_READY
    )
    assert len(ready_events) == 1


def test_resume_missing_dependency_checkpoint_fails_before_task_mutation() -> None:
    store = MemoryMetadataStore()
    _, b_run_id = _persist_completed_a_pending_b(
        store,
        persist_checkpoint=False,
    )
    workflow = _workflow(_task("A"), _task("B", "A"))

    with pytest.raises(ResumeError, match="no durable output checkpoint"):
        _runner(store, {"handlers:B": lambda: None}).resume(
            workflow,
            run_id=RUN_ID,
            reconciliation=_empty_report(),
        )

    assert store.get_task_run(b_run_id).status is TaskRunStatus.PENDING
    assert store.list_task_attempts(b_run_id) == ()
    assert tuple(event.event_sequence for event in store.list_events(RUN_ID)) == (1, 2)


def test_resume_confirmed_external_success_finishes_existing_attempt_without_reexecution() -> None:
    a_run_id = TaskRunId("resume-run:A")
    attempt_id = TaskAttemptId("resume-run:A:attempt-1")
    single_store = MemoryMetadataStore()
    with single_store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=RUN_ID,
                workflow_id=WorkflowId("workflow"),
                workflow_version="1",
                status=WorkflowRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=a_run_id,
                run_id=RUN_ID,
                task_id=TaskId("A"),
                status=TaskRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=attempt_id,
                task_run_id=a_run_id,
                attempt_number=1,
                status=TaskAttemptStatus.RUNNING,
                started_at=OLD,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("resume-run:event-1"),
                event_type=RuntimeEventType.WORKFLOW_STARTED,
                run_id=RUN_ID,
                occurred_at=OLD,
                event_sequence=1,
            )
        )
        uow.commit()

    resumed = _runner(single_store, {}).resume(
        _workflow(_task("A")),
        run_id=RUN_ID,
        reconciliation=_report(
            task_run_id=a_run_id,
            attempt_id=attempt_id,
            disposition=ReconciliationDisposition.CONFIRMED_SUCCEEDED,
        ),
    )

    assert resumed.run_id == RUN_ID
    assert resumed.status is WorkflowRunStatus.SUCCEEDED
    assert single_store.get_task_run(a_run_id).status is TaskRunStatus.SUCCEEDED
    attempts = single_store.list_task_attempts(a_run_id)
    assert len(attempts) == 1
    assert attempts[0].status is TaskAttemptStatus.SUCCEEDED


def test_resume_confirmed_external_failure_terminalizes_same_run_and_skips_downstream() -> None:
    store = MemoryMetadataStore()
    a_run_id, b_run_id, attempt_id = _persist_running_a_pending_b(store)
    workflow = _workflow(_task("A"), _task("B", "A"))

    resumed = _runner(store, {}).resume(
        workflow,
        run_id=RUN_ID,
        reconciliation=_report(
            task_run_id=a_run_id,
            attempt_id=attempt_id,
            disposition=ReconciliationDisposition.CONFIRMED_FAILED,
        ),
    )

    assert resumed.run_id == RUN_ID
    assert resumed.status is WorkflowRunStatus.FAILED
    assert store.get_task_run(a_run_id).status is TaskRunStatus.FAILED
    assert store.get_task_run(b_run_id).status is TaskRunStatus.SKIPPED
    assert store.get_task_run(b_run_id).skip_reason is SkipReason.DEPENDENCY_FAILED
    assert store.list_task_attempts(a_run_id)[0].error_category == "reconciliation"


def test_resume_confirmed_external_cancellation_cancels_same_run() -> None:
    store = MemoryMetadataStore()
    a_run_id, b_run_id, attempt_id = _persist_running_a_pending_b(store)
    workflow = _workflow(_task("A"), _task("B", "A"))

    resumed = _runner(store, {}).resume(
        workflow,
        run_id=RUN_ID,
        reconciliation=_report(
            task_run_id=a_run_id,
            attempt_id=attempt_id,
            disposition=ReconciliationDisposition.CONFIRMED_CANCELLED,
        ),
    )

    assert resumed.run_id == RUN_ID
    assert resumed.status is WorkflowRunStatus.CANCELLED
    assert store.get_task_run(a_run_id).status is TaskRunStatus.CANCELLED
    assert store.get_task_run(b_run_id).status is TaskRunStatus.CANCELLED
    assert store.list_task_attempts(a_run_id)[0].status is TaskAttemptStatus.CANCELLED


@pytest.mark.parametrize(
    "disposition",
    [
        ReconciliationDisposition.STILL_RUNNING,
        ReconciliationDisposition.MANUAL_REQUIRED,
    ],
)
def test_resume_blocks_unresolved_reconciliation_without_mutation(
    disposition: ReconciliationDisposition,
) -> None:
    store = MemoryMetadataStore()
    a_run_id, b_run_id, attempt_id = _persist_running_a_pending_b(store)
    workflow = _workflow(_task("A"), _task("B", "A"))

    with pytest.raises(ResumeError):
        _runner(store, {}).resume(
            workflow,
            run_id=RUN_ID,
            reconciliation=_report(
                task_run_id=a_run_id,
                attempt_id=attempt_id,
                disposition=disposition,
            ),
        )

    assert store.get_workflow_run(RUN_ID).status is WorkflowRunStatus.RUNNING
    assert store.get_task_run(a_run_id).status is TaskRunStatus.RUNNING
    assert store.get_task_run(b_run_id).status is TaskRunStatus.PENDING
    assert store.list_task_attempts(a_run_id)[0].status is TaskAttemptStatus.RUNNING


def test_resume_overdue_retry_wait_creates_next_attempt_on_same_task_run() -> None:
    store = MemoryMetadataStore()
    task_run_id = TaskRunId("resume-run:A")
    with store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=RUN_ID,
                workflow_id=WorkflowId("workflow"),
                workflow_version="1",
                status=WorkflowRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=task_run_id,
                run_id=RUN_ID,
                task_id=TaskId("A"),
                status=TaskRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("resume-run:A:attempt-1"),
                task_run_id=task_run_id,
                attempt_number=1,
                status=TaskAttemptStatus.FAILED,
                started_at=OLD,
                finished_at=OLD + timedelta(minutes=1),
                error_type="RuntimeError",
                error_message="temporary",
                error_category="RuntimeError",
                retry_eligible_at=OLD + timedelta(minutes=2),
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("resume-run:event-1"),
                event_type=RuntimeEventType.WORKFLOW_STARTED,
                run_id=RUN_ID,
                occurred_at=OLD,
                event_sequence=1,
            )
        )
        uow.add_event(
            RuntimeEvent(
                event_id=RuntimeEventId("resume-run:event-2"),
                event_type=RuntimeEventType.TASK_RETRYING,
                run_id=RUN_ID,
                occurred_at=OLD + timedelta(minutes=1),
                event_sequence=2,
                task_run_id=task_run_id,
                task_id=TaskId("A"),
                attempt_number=1,
                payload={
                    "retry_eligible_at": (OLD + timedelta(minutes=2)).isoformat(),
                    "next_attempt_number": 2,
                },
            )
        )
        uow.commit()

    resumed = _runner(store, {"handlers:A": lambda: "ok"}).resume(
        _workflow(_task("A")),
        run_id=RUN_ID,
        reconciliation=_empty_report(),
    )

    assert resumed.status is WorkflowRunStatus.SUCCEEDED
    attempts = store.list_task_attempts(task_run_id)
    assert tuple(attempt.attempt_number for attempt in attempts) == (1, 2)
    assert attempts[0].status is TaskAttemptStatus.FAILED
    assert attempts[1].status is TaskAttemptStatus.SUCCEEDED
    assert attempts[1].task_run_id == task_run_id


def test_resume_rejects_retry_wait_before_eligibility_without_mutation() -> None:
    store = MemoryMetadataStore()
    task_run_id = TaskRunId("resume-run:A")
    eligible_at = NOW + timedelta(minutes=5)
    with store.unit_of_work() as uow:
        uow.add_workflow_run(
            WorkflowRun(
                run_id=RUN_ID,
                workflow_id=WorkflowId("workflow"),
                workflow_version="1",
                status=WorkflowRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_run(
            TaskRun(
                task_run_id=task_run_id,
                run_id=RUN_ID,
                task_id=TaskId("A"),
                status=TaskRunStatus.RUNNING,
                created_at=OLD,
                started_at=OLD,
            )
        )
        uow.add_task_attempt(
            TaskAttempt(
                attempt_id=TaskAttemptId("resume-run:A:attempt-1"),
                task_run_id=task_run_id,
                attempt_number=1,
                status=TaskAttemptStatus.FAILED,
                started_at=OLD,
                finished_at=OLD + timedelta(minutes=1),
                error_type="RuntimeError",
                error_message="temporary",
                error_category="RuntimeError",
                retry_eligible_at=eligible_at,
            )
        )
        uow.commit()

    with pytest.raises(ResumeError, match="not eligible until"):
        _runner(store, {"handlers:A": lambda: "must-not-run"}).resume(
            _workflow(_task("A")),
            run_id=RUN_ID,
            reconciliation=_empty_report(),
        )

    attempts = store.list_task_attempts(task_run_id)
    assert len(attempts) == 1
    assert attempts[0].retry_eligible_at == eligible_at
    assert store.get_task_run(task_run_id).status is TaskRunStatus.RUNNING


def test_resume_rejects_workflow_definition_version_mismatch() -> None:
    store = MemoryMetadataStore()
    _persist_completed_a_pending_b(store)
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("workflow"),
        version="2",
        tasks=(_task("A"), _task("B", "A")),
    )

    with pytest.raises(ResumeError, match="identity/version"):
        _runner(store, {"handlers:B": lambda: None}).resume(
            workflow,
            run_id=RUN_ID,
            reconciliation=_empty_report(),
        )
