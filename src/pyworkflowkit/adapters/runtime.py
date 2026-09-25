"""Default runtime support adapters."""

from datetime import UTC, datetime
from time import sleep
from uuid import uuid4

from pyworkflowkit.domain.ids import (
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.ports.runtime import Clock, RuntimeIdFactory, Sleeper


class SystemClock:
    """UTC system clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class SystemSleeper:
    """Blocking wall-clock sleeper used for synchronous retry backoff."""

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        sleep(seconds)


class UuidRuntimeIdFactory:
    """UUID4-backed runtime identity factory."""

    def new_workflow_run_id(self) -> WorkflowRunId:
        return WorkflowRunId(str(uuid4()))

    def new_task_run_id(
        self,
        *,
        run_id: WorkflowRunId,
        task_id: TaskId,
    ) -> TaskRunId:
        del run_id, task_id
        return TaskRunId(str(uuid4()))

    def new_task_attempt_id(
        self,
        *,
        task_run_id: TaskRunId,
        attempt_number: int,
    ) -> TaskAttemptId:
        del task_run_id, attempt_number
        return TaskAttemptId(str(uuid4()))

    def new_runtime_event_id(
        self,
        *,
        run_id: WorkflowRunId,
        event_sequence: int,
    ) -> RuntimeEventId:
        del run_id, event_sequence
        return RuntimeEventId(str(uuid4()))


assert isinstance(SystemClock(), Clock)
assert isinstance(SystemSleeper(), Sleeper)
assert isinstance(UuidRuntimeIdFactory(), RuntimeIdFactory)


__all__ = ["SystemClock", "SystemSleeper", "UuidRuntimeIdFactory"]
