"""Tests for default runtime support adapters."""

from datetime import UTC

from pyworkflowkit.adapters.runtime import SystemClock, UuidRuntimeIdFactory
from pyworkflowkit.domain.ids import RuntimeEventId, TaskId, TaskRunId, WorkflowRunId
from pyworkflowkit.ports.runtime import Clock, RuntimeIdFactory


def test_system_clock_satisfies_clock_protocol_and_returns_aware_utc() -> None:
    clock = SystemClock()

    value = clock.now()

    assert isinstance(clock, Clock)
    assert value.tzinfo is UTC


def test_uuid_runtime_id_factory_satisfies_protocol_and_generates_unique_ids() -> None:
    factory = UuidRuntimeIdFactory()

    first_run_id = factory.new_workflow_run_id()
    second_run_id = factory.new_workflow_run_id()
    task_run_id = factory.new_task_run_id(
        run_id=WorkflowRunId("run"),
        task_id=TaskId("task"),
    )
    attempt_id = factory.new_task_attempt_id(
        task_run_id=TaskRunId("task-run"),
        attempt_number=1,
    )
    event_id = factory.new_runtime_event_id(
        run_id=WorkflowRunId("run"),
        event_sequence=1,
    )

    assert isinstance(factory, RuntimeIdFactory)
    assert first_run_id != second_run_id
    assert str(task_run_id)
    assert str(attempt_id)
    assert isinstance(event_id, str)
    assert RuntimeEventId(event_id) == event_id
