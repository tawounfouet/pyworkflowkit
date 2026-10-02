"""Internal TaskAttempt sequencing rules."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from pyworkflowkit.errors import RuntimeInvariantError
from pyworkflowkit.runtime.entities import TaskAttempt, TaskRun
from pyworkflowkit.runtime.identity import TaskAttemptId
from pyworkflowkit.states.enums import TaskAttemptStatus, TaskRunStatus


def next_task_attempt(
    task_run: TaskRun,
    existing_attempts: Sequence[TaskAttempt],
    *,
    attempt_id: TaskAttemptId,
    created_at: datetime,
) -> TaskAttempt:
    """Create the next attempt while preserving TaskRun identity."""

    if task_run.status not in {TaskRunStatus.READY, TaskRunStatus.RUNNING}:
        raise RuntimeInvariantError(
            reason=(
                f"cannot create attempt while TaskRun {task_run.task_run_id} "
                f"is {task_run.status.value}"
            )
        )

    attempts = tuple(existing_attempts)
    seen_ids: set[TaskAttemptId] = set()
    seen_numbers: set[int] = set()

    for attempt in attempts:
        if attempt.task_run_id != task_run.task_run_id:
            raise RuntimeInvariantError(
                reason="all existing attempts must belong to the same TaskRun"
            )
        if attempt.attempt_id in seen_ids:
            raise RuntimeInvariantError(reason="duplicate TaskAttemptId in attempt sequence")
        if attempt.attempt_number in seen_numbers:
            raise RuntimeInvariantError(reason="duplicate attempt_number in attempt sequence")
        seen_ids.add(attempt.attempt_id)
        seen_numbers.add(attempt.attempt_number)

    if attempt_id in seen_ids:
        raise RuntimeInvariantError(reason="new TaskAttemptId must be unique")

    ordered = tuple(sorted(attempts, key=lambda item: item.attempt_number))
    expected = tuple(range(1, len(ordered) + 1))
    actual = tuple(item.attempt_number for item in ordered)
    if actual != expected:
        raise RuntimeInvariantError(reason="existing attempt numbers must be contiguous from one")

    if ordered:
        previous = ordered[-1]
        if previous.status not in {
            TaskAttemptStatus.FAILED,
            TaskAttemptStatus.TIMED_OUT,
        }:
            raise RuntimeInvariantError(
                reason=(
                    "new attempt requires previous attempt to be FAILED or TIMED_OUT; "
                    f"got {previous.status.value}"
                )
            )

    return TaskAttempt(
        attempt_id=attempt_id,
        task_run_id=task_run.task_run_id,
        attempt_number=len(ordered) + 1,
        created_at=created_at,
    )


__all__: list[str] = []
