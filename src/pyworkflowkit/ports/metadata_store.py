"""Metadata persistence port and UnitOfWork contract."""

from collections.abc import Sequence
from types import TracebackType
from typing import Protocol, Self, runtime_checkable

from pyworkflowkit.domain.ids import TaskRunId, WorkflowRunId
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef


@runtime_checkable
class UnitOfWork(Protocol):
    """Atomic write boundary for runtime metadata."""

    def __enter__(self) -> Self:
        """Open this unit of work."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Rollback uncommitted work when leaving the context."""

    def add_workflow_run(self, run: WorkflowRun) -> None:
        """Stage a newly created workflow run."""

    def save_workflow_run(self, run: WorkflowRun) -> None:
        """Stage replacement state for an existing workflow run."""

    def add_task_run(self, task_run: TaskRun) -> None:
        """Stage a newly created task run."""

    def save_task_run(self, task_run: TaskRun) -> None:
        """Stage replacement state for an existing task run."""

    def add_task_attempt(self, attempt: TaskAttempt) -> None:
        """Stage a newly created task attempt."""

    def save_task_attempt(self, attempt: TaskAttempt) -> None:
        """Stage replacement state for an existing task attempt."""

    def add_event(self, event: RuntimeEvent) -> None:
        """Stage one immutable runtime event."""

    def add_artifact(
        self,
        *,
        task_run_id: TaskRunId,
        artifact: ArtifactReference,
    ) -> None:
        """Stage an artifact reference produced by a task run."""

    def add_external_run_ref(
        self,
        *,
        task_run_id: TaskRunId,
        external_ref: ExternalRunRef,
    ) -> None:
        """Stage a reference to an externally-owned execution."""

    def commit(self) -> None:
        """Atomically publish staged metadata."""

    def rollback(self) -> None:
        """Discard staged metadata."""


@runtime_checkable
class MetadataStore(Protocol):
    """Read model plus UnitOfWork factory for runtime metadata."""

    def unit_of_work(self) -> UnitOfWork:
        """Create a fresh atomic write boundary."""

    def get_workflow_run(self, run_id: WorkflowRunId) -> WorkflowRun:
        """Load a workflow run or raise a not-found error."""

    def get_task_run(self, task_run_id: TaskRunId) -> TaskRun:
        """Load a task run or raise a not-found error."""

    def list_task_runs(self, run_id: WorkflowRunId) -> Sequence[TaskRun]:
        """Return task runs belonging to one workflow run."""

    def list_task_attempts(self, task_run_id: TaskRunId) -> Sequence[TaskAttempt]:
        """Return task attempts ordered by attempt number."""

    def list_events(self, run_id: WorkflowRunId) -> Sequence[RuntimeEvent]:
        """Return runtime events in deterministic event order."""

    def list_artifacts(self, task_run_id: TaskRunId) -> Sequence[ArtifactReference]:
        """Return artifacts associated with one task run."""

    def list_external_run_refs(self, task_run_id: TaskRunId) -> Sequence[ExternalRunRef]:
        """Return external execution references associated with one task run."""


__all__ = ["MetadataStore", "UnitOfWork"]
