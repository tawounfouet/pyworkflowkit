"""Runtime support ports for deterministic workflow execution."""

from datetime import datetime
from typing import Protocol, runtime_checkable

from pyworkflowkit.domain.ids import (
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowRunId,
)


@runtime_checkable
class Clock(Protocol):
    """Source of timezone-aware runtime timestamps."""

    def now(self) -> datetime:
        """Return the current timezone-aware datetime."""


@runtime_checkable
class RuntimeIdFactory(Protocol):
    """Factory for runtime aggregate/entity/event identities."""

    def new_workflow_run_id(self) -> WorkflowRunId:
        """Create a new WorkflowRun identity."""

    def new_task_run_id(
        self,
        *,
        run_id: WorkflowRunId,
        task_id: TaskId,
    ) -> TaskRunId:
        """Create a TaskRun identity for one workflow task."""

    def new_task_attempt_id(
        self,
        *,
        task_run_id: TaskRunId,
        attempt_number: int,
    ) -> TaskAttemptId:
        """Create a TaskAttempt identity."""

    def new_runtime_event_id(
        self,
        *,
        run_id: WorkflowRunId,
        event_sequence: int,
    ) -> RuntimeEventId:
        """Create a RuntimeEvent identity."""


__all__ = ["Clock", "RuntimeIdFactory"]
