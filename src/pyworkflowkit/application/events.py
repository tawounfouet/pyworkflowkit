"""Deterministic runtime-event construction."""

from collections.abc import Mapping
from datetime import datetime

from pyworkflowkit.domain.enums import RuntimeEventType
from pyworkflowkit.domain.ids import TaskId, TaskRunId, WorkflowRunId
from pyworkflowkit.domain.runtime import RuntimeEvent
from pyworkflowkit.ports.runtime import RuntimeIdFactory

_WORKFLOW_EVENT_TYPES = frozenset(
    {
        RuntimeEventType.WORKFLOW_STARTED,
        RuntimeEventType.WORKFLOW_SUCCEEDED,
        RuntimeEventType.WORKFLOW_FAILED,
        RuntimeEventType.WORKFLOW_CANCELLED,
    }
)

_TASK_EVENT_TYPES = frozenset(
    {
        RuntimeEventType.TASK_READY,
        RuntimeEventType.TASK_STARTED,
        RuntimeEventType.TASK_RETRYING,
        RuntimeEventType.TASK_SUCCEEDED,
        RuntimeEventType.TASK_FAILED,
        RuntimeEventType.TASK_SKIPPED,
    }
)


class RuntimeEventFactory:
    """Create monotonically sequenced RuntimeEvent values for one run."""

    def __init__(
        self,
        *,
        run_id: WorkflowRunId,
        id_factory: RuntimeIdFactory,
    ) -> None:
        self._run_id = run_id
        self._id_factory = id_factory
        self._next_sequence = 1

    def create(
        self,
        *,
        event_type: RuntimeEventType,
        occurred_at: datetime,
        task_run_id: TaskRunId | None = None,
        task_id: TaskId | None = None,
        attempt_number: int | None = None,
        payload: Mapping[str, object] | None = None,
    ) -> RuntimeEvent:
        """Create the next event while enforcing workflow/task event context."""
        if event_type in _WORKFLOW_EVENT_TYPES:
            if task_run_id is not None or task_id is not None or attempt_number is not None:
                raise ValueError("workflow events cannot carry task context")
        elif event_type in _TASK_EVENT_TYPES:
            if task_run_id is None or task_id is None:
                raise ValueError("task events require task_run_id and task_id")
        else:
            raise ValueError(f"unsupported runtime event type: {event_type}")

        sequence = self._next_sequence
        event = RuntimeEvent(
            event_id=self._id_factory.new_runtime_event_id(
                run_id=self._run_id,
                event_sequence=sequence,
            ),
            event_type=event_type,
            run_id=self._run_id,
            occurred_at=occurred_at,
            event_sequence=sequence,
            task_run_id=task_run_id,
            task_id=task_id,
            attempt_number=attempt_number,
            payload=payload or {},
        )
        self._next_sequence += 1
        return event


__all__ = ["RuntimeEventFactory"]
