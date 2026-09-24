"""Tests for runtime entities and immutable runtime events."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from operator import setitem

import pytest

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
from pyworkflowkit.domain.runtime import (
    RuntimeEvent,
    TaskAttempt,
    TaskRun,
    WorkflowRun,
)


def aware_datetime() -> datetime:
    return datetime(2026, 9, 25, 0, 0, tzinfo=UTC)


def test_workflow_run_defaults_to_pending() -> None:
    run = WorkflowRun(
        run_id=WorkflowRunId("run-1"),
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
    )

    assert run.status is WorkflowRunStatus.PENDING
    assert run.started_at is None
    assert run.finished_at is None


def test_workflow_run_defensively_copies_parameters() -> None:
    parameters = {"source": "input.csv"}
    run = WorkflowRun(
        run_id=WorkflowRunId("run-1"),
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
        parameters=parameters,
    )

    parameters["source"] = "changed.csv"

    assert run.parameters["source"] == "input.csv"
    with pytest.raises(TypeError):
        setitem(run.parameters, "source", "mutated.csv")


@pytest.mark.parametrize(
    "field_name,kwargs",
    [
        ("run_id", {"run_id": WorkflowRunId("")}),
        ("workflow_id", {"workflow_id": WorkflowId(" ")}),
        ("workflow_version", {"workflow_version": ""}),
    ],
)
def test_workflow_run_rejects_blank_identity_fields(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "run_id": WorkflowRunId("run-1"),
        "workflow_id": WorkflowId("workflow"),
        "workflow_version": "1",
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=field_name):
        WorkflowRun(**values)  # type: ignore[arg-type]


def test_workflow_run_rejects_invalid_status_type() -> None:
    with pytest.raises(TypeError, match="WorkflowRunStatus"):
        WorkflowRun(
            run_id=WorkflowRunId("run-1"),
            workflow_id=WorkflowId("workflow"),
            workflow_version="1",
            status="PENDING",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("field_name", ["created_at", "started_at", "finished_at"])
def test_workflow_run_rejects_naive_timestamps(field_name: str) -> None:
    kwargs = {field_name: datetime(2026, 9, 25)}

    with pytest.raises(ValueError, match=field_name):
        WorkflowRun(
            run_id=WorkflowRunId("run-1"),
            workflow_id=WorkflowId("workflow"),
            workflow_version="1",
            **kwargs,  # type: ignore[arg-type]
        )


def test_pending_workflow_run_rejects_started_timestamp() -> None:
    with pytest.raises(ValueError, match="PENDING"):
        WorkflowRun(
            run_id=WorkflowRunId("run-1"),
            workflow_id=WorkflowId("workflow"),
            workflow_version="1",
            started_at=aware_datetime(),
        )


def test_running_workflow_run_rejects_finished_timestamp() -> None:
    with pytest.raises(ValueError, match="RUNNING"):
        WorkflowRun(
            run_id=WorkflowRunId("run-1"),
            workflow_id=WorkflowId("workflow"),
            workflow_version="1",
            status=WorkflowRunStatus.RUNNING,
            finished_at=aware_datetime(),
        )


@pytest.mark.parametrize(
    "status",
    [
        WorkflowRunStatus.SUCCEEDED,
        WorkflowRunStatus.FAILED,
        WorkflowRunStatus.CANCELLED,
    ],
)
def test_terminal_workflow_run_requires_finished_timestamp(
    status: WorkflowRunStatus,
) -> None:
    with pytest.raises(ValueError, match="Terminal WorkflowRun"):
        WorkflowRun(
            run_id=WorkflowRunId("run-1"),
            workflow_id=WorkflowId("workflow"),
            workflow_version="1",
            status=status,
        )


def test_terminal_workflow_run_accepts_finished_timestamp() -> None:
    run = WorkflowRun(
        run_id=WorkflowRunId("run-1"),
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
        status=WorkflowRunStatus.SUCCEEDED,
        finished_at=aware_datetime(),
    )

    assert run.status is WorkflowRunStatus.SUCCEEDED


def test_task_run_defaults_to_pending() -> None:
    task_run = TaskRun(
        task_run_id=TaskRunId("task-run-1"),
        run_id=WorkflowRunId("run-1"),
        task_id=TaskId("fetch"),
    )

    assert task_run.status is TaskRunStatus.PENDING
    assert task_run.skip_reason is None


@pytest.mark.parametrize(
    "field_name,kwargs",
    [
        ("task_run_id", {"task_run_id": TaskRunId("")}),
        ("run_id", {"run_id": WorkflowRunId(" ")}),
        ("task_id", {"task_id": TaskId("")}),
    ],
)
def test_task_run_rejects_blank_identity_fields(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "task_run_id": TaskRunId("task-run-1"),
        "run_id": WorkflowRunId("run-1"),
        "task_id": TaskId("fetch"),
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=field_name):
        TaskRun(**values)  # type: ignore[arg-type]


def test_task_run_rejects_invalid_status_type() -> None:
    with pytest.raises(TypeError, match="TaskRunStatus"):
        TaskRun(
            task_run_id=TaskRunId("task-run-1"),
            run_id=WorkflowRunId("run-1"),
            task_id=TaskId("fetch"),
            status="PENDING",  # type: ignore[arg-type]
        )


def test_task_run_rejects_invalid_skip_reason_type() -> None:
    with pytest.raises(TypeError, match="SkipReason"):
        TaskRun(
            task_run_id=TaskRunId("task-run-1"),
            run_id=WorkflowRunId("run-1"),
            task_id=TaskId("fetch"),
            skip_reason="CONDITION_FALSE",  # type: ignore[arg-type]
        )


def test_skipped_task_run_requires_skip_reason() -> None:
    with pytest.raises(ValueError, match="skip_reason"):
        TaskRun(
            task_run_id=TaskRunId("task-run-1"),
            run_id=WorkflowRunId("run-1"),
            task_id=TaskId("fetch"),
            status=TaskRunStatus.SKIPPED,
            finished_at=aware_datetime(),
        )


def test_skip_reason_is_only_valid_for_skipped_task_run() -> None:
    with pytest.raises(ValueError, match="only valid"):
        TaskRun(
            task_run_id=TaskRunId("task-run-1"),
            run_id=WorkflowRunId("run-1"),
            task_id=TaskId("fetch"),
            skip_reason=SkipReason.CONDITION_FALSE,
        )


def test_skipped_task_run_accepts_reason_and_finished_timestamp() -> None:
    task_run = TaskRun(
        task_run_id=TaskRunId("task-run-1"),
        run_id=WorkflowRunId("run-1"),
        task_id=TaskId("fetch"),
        status=TaskRunStatus.SKIPPED,
        skip_reason=SkipReason.CONDITION_FALSE,
        finished_at=aware_datetime(),
    )

    assert task_run.skip_reason is SkipReason.CONDITION_FALSE


@pytest.mark.parametrize("status", [TaskRunStatus.PENDING, TaskRunStatus.READY])
def test_unstarted_task_states_reject_finished_timestamp(
    status: TaskRunStatus,
) -> None:
    with pytest.raises(ValueError, match=status.value):
        TaskRun(
            task_run_id=TaskRunId("task-run-1"),
            run_id=WorkflowRunId("run-1"),
            task_id=TaskId("fetch"),
            status=status,
            finished_at=aware_datetime(),
        )


def test_running_task_run_rejects_finished_timestamp() -> None:
    with pytest.raises(ValueError, match="RUNNING"):
        TaskRun(
            task_run_id=TaskRunId("task-run-1"),
            run_id=WorkflowRunId("run-1"),
            task_id=TaskId("fetch"),
            status=TaskRunStatus.RUNNING,
            finished_at=aware_datetime(),
        )


@pytest.mark.parametrize(
    "status",
    [
        TaskRunStatus.SUCCEEDED,
        TaskRunStatus.FAILED,
        TaskRunStatus.CANCELLED,
    ],
)
def test_terminal_task_run_requires_finished_timestamp(
    status: TaskRunStatus,
) -> None:
    with pytest.raises(ValueError, match="Terminal TaskRun"):
        TaskRun(
            task_run_id=TaskRunId("task-run-1"),
            run_id=WorkflowRunId("run-1"),
            task_id=TaskId("fetch"),
            status=status,
        )


def test_task_run_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="created_at"):
        TaskRun(
            task_run_id=TaskRunId("task-run-1"),
            run_id=WorkflowRunId("run-1"),
            task_id=TaskId("fetch"),
            created_at=datetime(2026, 9, 25),
        )


def test_task_attempt_defaults_to_running() -> None:
    attempt = TaskAttempt(
        attempt_id=TaskAttemptId("attempt-1"),
        task_run_id=TaskRunId("task-run-1"),
        attempt_number=1,
    )

    assert attempt.status is TaskAttemptStatus.RUNNING
    assert attempt.finished_at is None


@pytest.mark.parametrize("attempt_number", [0, -1])
def test_task_attempt_rejects_non_positive_attempt_number(
    attempt_number: int,
) -> None:
    with pytest.raises(ValueError, match="attempt_number"):
        TaskAttempt(
            attempt_id=TaskAttemptId("attempt-1"),
            task_run_id=TaskRunId("task-run-1"),
            attempt_number=attempt_number,
        )


def test_task_attempt_rejects_boolean_attempt_number() -> None:
    with pytest.raises(TypeError, match="attempt_number"):
        TaskAttempt(
            attempt_id=TaskAttemptId("attempt-1"),
            task_run_id=TaskRunId("task-run-1"),
            attempt_number=True,
        )


@pytest.mark.parametrize(
    "field_name,kwargs",
    [
        ("attempt_id", {"attempt_id": TaskAttemptId("")}),
        ("task_run_id", {"task_run_id": TaskRunId(" ")}),
    ],
)
def test_task_attempt_rejects_blank_identity_fields(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "attempt_id": TaskAttemptId("attempt-1"),
        "task_run_id": TaskRunId("task-run-1"),
        "attempt_number": 1,
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=field_name):
        TaskAttempt(**values)  # type: ignore[arg-type]


def test_task_attempt_rejects_invalid_status_type() -> None:
    with pytest.raises(TypeError, match="TaskAttemptStatus"):
        TaskAttempt(
            attempt_id=TaskAttemptId("attempt-1"),
            task_run_id=TaskRunId("task-run-1"),
            attempt_number=1,
            status="RUNNING",  # type: ignore[arg-type]
        )


def test_running_task_attempt_rejects_finished_timestamp() -> None:
    with pytest.raises(ValueError, match="RUNNING"):
        TaskAttempt(
            attempt_id=TaskAttemptId("attempt-1"),
            task_run_id=TaskRunId("task-run-1"),
            attempt_number=1,
            finished_at=aware_datetime(),
        )


@pytest.mark.parametrize(
    "status",
    [
        TaskAttemptStatus.SUCCEEDED,
        TaskAttemptStatus.FAILED,
        TaskAttemptStatus.CANCELLED,
    ],
)
def test_terminal_task_attempt_requires_finished_timestamp(
    status: TaskAttemptStatus,
) -> None:
    with pytest.raises(ValueError, match="Terminal TaskAttempt"):
        TaskAttempt(
            attempt_id=TaskAttemptId("attempt-1"),
            task_run_id=TaskRunId("task-run-1"),
            attempt_number=1,
            status=status,
        )


def test_task_attempt_defensively_copies_error_metadata() -> None:
    metadata = {"provider_code": "E_TEMP"}
    attempt = TaskAttempt(
        attempt_id=TaskAttemptId("attempt-1"),
        task_run_id=TaskRunId("task-run-1"),
        attempt_number=1,
        error_metadata=metadata,
    )

    metadata["provider_code"] = "changed"

    assert attempt.error_metadata["provider_code"] == "E_TEMP"
    with pytest.raises(TypeError):
        setitem(attempt.error_metadata, "provider_code", "mutated")


def test_task_attempt_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="started_at"):
        TaskAttempt(
            attempt_id=TaskAttemptId("attempt-1"),
            task_run_id=TaskRunId("task-run-1"),
            attempt_number=1,
            started_at=datetime(2026, 9, 25),
        )


def test_runtime_event_is_immutable_and_freezes_payload() -> None:
    payload = {"key": "value"}
    event = RuntimeEvent(
        event_id=RuntimeEventId("event-1"),
        event_type=RuntimeEventType.WORKFLOW_STARTED,
        run_id=WorkflowRunId("run-1"),
        occurred_at=aware_datetime(),
        payload=payload,
    )

    payload["key"] = "changed"

    assert event.payload["key"] == "value"
    with pytest.raises(TypeError):
        setitem(event.payload, "key", "mutated")
    with pytest.raises(FrozenInstanceError):
        event.event_sequence = 2  # type: ignore[misc]


def test_runtime_event_rejects_naive_occurred_at() -> None:
    with pytest.raises(ValueError, match="occurred_at"):
        RuntimeEvent(
            event_id=RuntimeEventId("event-1"),
            event_type=RuntimeEventType.WORKFLOW_STARTED,
            run_id=WorkflowRunId("run-1"),
            occurred_at=datetime(2026, 9, 25),
        )


@pytest.mark.parametrize(
    "field_name,kwargs",
    [
        ("event_id", {"event_id": RuntimeEventId("")}),
        ("run_id", {"run_id": WorkflowRunId(" ")}),
    ],
)
def test_runtime_event_rejects_blank_identity_fields(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "event_id": RuntimeEventId("event-1"),
        "event_type": RuntimeEventType.WORKFLOW_STARTED,
        "run_id": WorkflowRunId("run-1"),
        "occurred_at": aware_datetime(),
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=field_name):
        RuntimeEvent(**values)  # type: ignore[arg-type]


def test_runtime_event_rejects_invalid_event_type() -> None:
    with pytest.raises(TypeError, match="RuntimeEventType"):
        RuntimeEvent(
            event_id=RuntimeEventId("event-1"),
            event_type="WORKFLOW_STARTED",  # type: ignore[arg-type]
            run_id=WorkflowRunId("run-1"),
            occurred_at=aware_datetime(),
        )


def test_runtime_event_validates_optional_task_ids() -> None:
    with pytest.raises(ValueError, match="task_run_id"):
        RuntimeEvent(
            event_id=RuntimeEventId("event-1"),
            event_type=RuntimeEventType.TASK_STARTED,
            run_id=WorkflowRunId("run-1"),
            occurred_at=aware_datetime(),
            task_run_id=TaskRunId(""),
            task_id=TaskId("fetch"),
        )


@pytest.mark.parametrize(
    "field_name,kwargs",
    [
        ("event_sequence", {"event_sequence": 0}),
        ("attempt_number", {"attempt_number": 0}),
    ],
)
def test_runtime_event_rejects_non_positive_sequence_values(
    field_name: str,
    kwargs: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "event_id": RuntimeEventId("event-1"),
        "event_type": RuntimeEventType.TASK_STARTED,
        "run_id": WorkflowRunId("run-1"),
        "occurred_at": aware_datetime(),
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=field_name):
        RuntimeEvent(**values)  # type: ignore[arg-type]


def test_runtime_event_rejects_boolean_sequence_value() -> None:
    with pytest.raises(TypeError, match="event_sequence"):
        RuntimeEvent(
            event_id=RuntimeEventId("event-1"),
            event_type=RuntimeEventType.WORKFLOW_STARTED,
            run_id=WorkflowRunId("run-1"),
            occurred_at=aware_datetime(),
            event_sequence=True,
        )


def test_runtime_event_accepts_task_attempt_context() -> None:
    event = RuntimeEvent(
        event_id=RuntimeEventId("event-1"),
        event_type=RuntimeEventType.TASK_STARTED,
        run_id=WorkflowRunId("run-1"),
        occurred_at=aware_datetime(),
        event_sequence=3,
        task_run_id=TaskRunId("task-run-1"),
        task_id=TaskId("fetch"),
        attempt_number=1,
    )

    assert event.event_sequence == 3
    assert event.task_id == TaskId("fetch")
    assert event.attempt_number == 1
