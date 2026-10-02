"""Injectable V2 runtime clock, identity and retry-wait services."""

from __future__ import annotations

from datetime import UTC, datetime
from time import sleep
from typing import Protocol, runtime_checkable

from pyworkflowkit.runtime.identity import (
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime:
        """Return one timezone-aware runtime timestamp."""


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@runtime_checkable
class RetryWaiter(Protocol):
    """Wait boundary used by retry execution."""

    def wait(self, seconds: float) -> None:
        """Wait for the requested retry delay."""


class SystemRetryWaiter:
    def wait(self, seconds: float) -> None:
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise TypeError("seconds must be a number")
        if seconds < 0:
            raise ValueError("seconds must be greater than or equal to 0")
        if seconds:
            sleep(seconds)


@runtime_checkable
class RuntimeIdentityFactory(Protocol):
    def new_workflow_run_id(self) -> WorkflowRunId: ...

    def new_task_run_id(self) -> TaskRunId: ...

    def new_task_attempt_id(self) -> TaskAttemptId: ...

    def new_correlation_id(self) -> CorrelationId: ...


class UuidRuntimeIdentityFactory:
    def new_workflow_run_id(self) -> WorkflowRunId:
        return WorkflowRunId.new()

    def new_task_run_id(self) -> TaskRunId:
        return TaskRunId.new()

    def new_task_attempt_id(self) -> TaskAttemptId:
        return TaskAttemptId.new()

    def new_correlation_id(self) -> CorrelationId:
        return CorrelationId.new()


__all__ = [
    "Clock",
    "RetryWaiter",
    "RuntimeIdentityFactory",
    "SystemClock",
    "SystemRetryWaiter",
    "UuidRuntimeIdentityFactory",
]
