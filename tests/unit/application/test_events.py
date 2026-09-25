"""Tests for deterministic runtime-event construction."""

from datetime import UTC, datetime

import pytest

from pyworkflowkit.application.events import RuntimeEventFactory
from pyworkflowkit.domain.enums import RuntimeEventType
from pyworkflowkit.domain.ids import (
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.ports.runtime import RuntimeIdFactory

NOW = datetime(2026, 9, 25, 20, 0, tzinfo=UTC)


class DeterministicIdFactory:
    def new_workflow_run_id(self) -> WorkflowRunId:
        return WorkflowRunId("run")

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
        return TaskAttemptId(f"{task_run_id}:{attempt_number}")

    def new_runtime_event_id(
        self,
        *,
        run_id: WorkflowRunId,
        event_sequence: int,
    ) -> RuntimeEventId:
        return RuntimeEventId(f"{run_id}:event-{event_sequence}")


def test_event_factory_assigns_monotonic_sequence_and_deterministic_ids() -> None:
    ids = DeterministicIdFactory()
    assert isinstance(ids, RuntimeIdFactory)
    factory = RuntimeEventFactory(
        run_id=WorkflowRunId("run"),
        id_factory=ids,
    )

    first = factory.create(
        event_type=RuntimeEventType.WORKFLOW_STARTED,
        occurred_at=NOW,
    )
    second = factory.create(
        event_type=RuntimeEventType.TASK_READY,
        occurred_at=NOW,
        task_run_id=TaskRunId("task-run"),
        task_id=TaskId("A"),
    )

    assert first.event_sequence == 1
    assert first.event_id == RuntimeEventId("run:event-1")
    assert second.event_sequence == 2
    assert second.event_id == RuntimeEventId("run:event-2")


def test_event_factory_rejects_task_context_on_workflow_event() -> None:
    factory = RuntimeEventFactory(
        run_id=WorkflowRunId("run"),
        id_factory=DeterministicIdFactory(),
    )

    with pytest.raises(ValueError, match="workflow events"):
        factory.create(
            event_type=RuntimeEventType.WORKFLOW_STARTED,
            occurred_at=NOW,
            task_run_id=TaskRunId("task-run"),
            task_id=TaskId("A"),
        )


def test_event_factory_requires_task_context_for_task_event() -> None:
    factory = RuntimeEventFactory(
        run_id=WorkflowRunId("run"),
        id_factory=DeterministicIdFactory(),
    )

    with pytest.raises(ValueError, match="task events"):
        factory.create(
            event_type=RuntimeEventType.TASK_STARTED,
            occurred_at=NOW,
        )
