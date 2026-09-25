"""Transactional in-memory metadata store."""

from dataclasses import dataclass, field
from types import MappingProxyType
from types import TracebackType
from typing import Self

from pyworkflowkit.domain.ids import (
    ArtifactId,
    ExternalRunRefId,
    RuntimeEventId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef
from pyworkflowkit.errors import (
    DuplicateMetadataError,
    MetadataNotFoundError,
    UnitOfWorkStateError,
)
from pyworkflowkit.ports.metadata_store import MetadataStore, UnitOfWork


@dataclass(slots=True)
class _MemoryState:
    workflow_runs: dict[WorkflowRunId, WorkflowRun] = field(default_factory=dict)
    task_runs: dict[TaskRunId, TaskRun] = field(default_factory=dict)
    task_attempts: dict[TaskAttemptId, TaskAttempt] = field(default_factory=dict)
    events: dict[RuntimeEventId, RuntimeEvent] = field(default_factory=dict)
    artifacts: dict[ArtifactId, tuple[TaskRunId, ArtifactReference]] = field(
        default_factory=dict
    )
    external_refs: dict[
        ExternalRunRefId,
        tuple[TaskRunId, ExternalRunRef],
    ] = field(default_factory=dict)


class MemoryMetadataStore:
    """In-memory MetadataStore with explicit transactional write boundaries."""

    def __init__(self) -> None:
        self._state = _MemoryState()

    def unit_of_work(self) -> UnitOfWork:
        return MemoryUnitOfWork(self)

    def get_workflow_run(self, run_id: WorkflowRunId) -> WorkflowRun:
        try:
            return _clone_workflow_run(self._state.workflow_runs[run_id])
        except KeyError as exc:
            raise MetadataNotFoundError(
                entity_type="WorkflowRun",
                entity_id=str(run_id),
            ) from exc

    def get_task_run(self, task_run_id: TaskRunId) -> TaskRun:
        try:
            return _clone_task_run(self._state.task_runs[task_run_id])
        except KeyError as exc:
            raise MetadataNotFoundError(
                entity_type="TaskRun",
                entity_id=str(task_run_id),
            ) from exc

    def list_task_runs(self, run_id: WorkflowRunId) -> tuple[TaskRun, ...]:
        values = (
            _clone_task_run(task_run)
            for task_run in self._state.task_runs.values()
            if task_run.run_id == run_id
        )
        return tuple(sorted(values, key=lambda task_run: str(task_run.task_id)))

    def list_task_attempts(self, task_run_id: TaskRunId) -> tuple[TaskAttempt, ...]:
        values = (
            _clone_task_attempt(attempt)
            for attempt in self._state.task_attempts.values()
            if attempt.task_run_id == task_run_id
        )
        return tuple(sorted(values, key=lambda attempt: attempt.attempt_number))

    def list_events(self, run_id: WorkflowRunId) -> tuple[RuntimeEvent, ...]:
        values = (
            event for event in self._state.events.values() if event.run_id == run_id
        )
        return tuple(sorted(values, key=_event_sort_key))

    def list_artifacts(self, task_run_id: TaskRunId) -> tuple[ArtifactReference, ...]:
        values = (
            artifact
            for owner_task_run_id, artifact in self._state.artifacts.values()
            if owner_task_run_id == task_run_id
        )
        return tuple(sorted(values, key=lambda artifact: str(artifact.artifact_id)))

    def list_external_run_refs(
        self,
        task_run_id: TaskRunId,
    ) -> tuple[ExternalRunRef, ...]:
        values = (
            external_ref
            for owner_task_run_id, external_ref in self._state.external_refs.values()
            if owner_task_run_id == task_run_id
        )
        return tuple(
            sorted(values, key=lambda external_ref: str(external_ref.external_ref_id))
        )


class MemoryUnitOfWork:
    """Copy-on-write UnitOfWork for MemoryMetadataStore."""

    def __init__(self, store: MemoryMetadataStore) -> None:
        self._store = store
        self._staged_state: _MemoryState | None = None
        self._active = False

    def __enter__(self) -> Self:
        if self._active:
            raise UnitOfWorkStateError(reason="unit of work is already active")
        self._staged_state = _clone_state(self._store._state)
        self._active = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        del exc_type, exc_value, traceback
        if self._active:
            self.rollback()
        return None

    def add_workflow_run(self, run: WorkflowRun) -> None:
        state = self._require_state()
        if run.run_id in state.workflow_runs:
            raise DuplicateMetadataError(
                entity_type="WorkflowRun",
                entity_id=str(run.run_id),
            )
        state.workflow_runs[run.run_id] = _clone_workflow_run(run)

    def save_workflow_run(self, run: WorkflowRun) -> None:
        state = self._require_state()
        if run.run_id not in state.workflow_runs:
            raise MetadataNotFoundError(
                entity_type="WorkflowRun",
                entity_id=str(run.run_id),
            )
        state.workflow_runs[run.run_id] = _clone_workflow_run(run)

    def add_task_run(self, task_run: TaskRun) -> None:
        state = self._require_state()
        if task_run.task_run_id in state.task_runs:
            raise DuplicateMetadataError(
                entity_type="TaskRun",
                entity_id=str(task_run.task_run_id),
            )
        if task_run.run_id not in state.workflow_runs:
            raise MetadataNotFoundError(
                entity_type="WorkflowRun",
                entity_id=str(task_run.run_id),
            )
        state.task_runs[task_run.task_run_id] = _clone_task_run(task_run)

    def save_task_run(self, task_run: TaskRun) -> None:
        state = self._require_state()
        if task_run.task_run_id not in state.task_runs:
            raise MetadataNotFoundError(
                entity_type="TaskRun",
                entity_id=str(task_run.task_run_id),
            )
        state.task_runs[task_run.task_run_id] = _clone_task_run(task_run)

    def add_task_attempt(self, attempt: TaskAttempt) -> None:
        state = self._require_state()
        if attempt.attempt_id in state.task_attempts:
            raise DuplicateMetadataError(
                entity_type="TaskAttempt",
                entity_id=str(attempt.attempt_id),
            )
        if attempt.task_run_id not in state.task_runs:
            raise MetadataNotFoundError(
                entity_type="TaskRun",
                entity_id=str(attempt.task_run_id),
            )

        for existing in state.task_attempts.values():
            if (
                existing.task_run_id == attempt.task_run_id
                and existing.attempt_number == attempt.attempt_number
            ):
                raise DuplicateMetadataError(
                    entity_type="TaskAttemptNumber",
                    entity_id=(
                        f"{attempt.task_run_id}:{attempt.attempt_number}"
                    ),
                )

        state.task_attempts[attempt.attempt_id] = _clone_task_attempt(attempt)

    def add_event(self, event: RuntimeEvent) -> None:
        state = self._require_state()
        if event.event_id in state.events:
            raise DuplicateMetadataError(
                entity_type="RuntimeEvent",
                entity_id=str(event.event_id),
            )
        if event.run_id not in state.workflow_runs:
            raise MetadataNotFoundError(
                entity_type="WorkflowRun",
                entity_id=str(event.run_id),
            )
        state.events[event.event_id] = event

    def add_artifact(
        self,
        *,
        task_run_id: TaskRunId,
        artifact: ArtifactReference,
    ) -> None:
        state = self._require_state()
        if task_run_id not in state.task_runs:
            raise MetadataNotFoundError(
                entity_type="TaskRun",
                entity_id=str(task_run_id),
            )
        if artifact.artifact_id in state.artifacts:
            raise DuplicateMetadataError(
                entity_type="Artifact",
                entity_id=str(artifact.artifact_id),
            )
        state.artifacts[artifact.artifact_id] = (task_run_id, artifact)

    def add_external_run_ref(
        self,
        *,
        task_run_id: TaskRunId,
        external_ref: ExternalRunRef,
    ) -> None:
        state = self._require_state()
        if task_run_id not in state.task_runs:
            raise MetadataNotFoundError(
                entity_type="TaskRun",
                entity_id=str(task_run_id),
            )
        if external_ref.external_ref_id in state.external_refs:
            raise DuplicateMetadataError(
                entity_type="ExternalRunRef",
                entity_id=str(external_ref.external_ref_id),
            )
        state.external_refs[external_ref.external_ref_id] = (
            task_run_id,
            external_ref,
        )

    def commit(self) -> None:
        state = self._require_state()
        self._store._state = state
        self._staged_state = None
        self._active = False

    def rollback(self) -> None:
        if not self._active:
            raise UnitOfWorkStateError(reason="unit of work is not active")
        self._staged_state = None
        self._active = False

    def _require_state(self) -> _MemoryState:
        if not self._active or self._staged_state is None:
            raise UnitOfWorkStateError(
                reason="unit of work must be entered before use"
            )
        return self._staged_state


def _clone_state(state: _MemoryState) -> _MemoryState:
    return _MemoryState(
        workflow_runs={
            run_id: _clone_workflow_run(run)
            for run_id, run in state.workflow_runs.items()
        },
        task_runs={
            task_run_id: _clone_task_run(task_run)
            for task_run_id, task_run in state.task_runs.items()
        },
        task_attempts={
            attempt_id: _clone_task_attempt(attempt)
            for attempt_id, attempt in state.task_attempts.items()
        },
        events=dict(state.events),
        artifacts=dict(state.artifacts),
        external_refs=dict(state.external_refs),
    )


def _clone_workflow_run(run: WorkflowRun) -> WorkflowRun:
    return WorkflowRun(
        run_id=run.run_id,
        workflow_id=run.workflow_id,
        workflow_version=run.workflow_version,
        status=run.status,
        parameters=dict(run.parameters),
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _clone_task_run(task_run: TaskRun) -> TaskRun:
    return TaskRun(
        task_run_id=task_run.task_run_id,
        run_id=task_run.run_id,
        task_id=task_run.task_id,
        status=task_run.status,
        skip_reason=task_run.skip_reason,
        created_at=task_run.created_at,
        started_at=task_run.started_at,
        finished_at=task_run.finished_at,
    )


def _clone_task_attempt(attempt: TaskAttempt) -> TaskAttempt:
    return TaskAttempt(
        attempt_id=attempt.attempt_id,
        task_run_id=attempt.task_run_id,
        attempt_number=attempt.attempt_number,
        status=attempt.status,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        error_type=attempt.error_type,
        error_message=attempt.error_message,
        error_category=attempt.error_category,
        error_metadata=dict(attempt.error_metadata),
    )


def _event_sort_key(event: RuntimeEvent) -> tuple[int, str]:
    sequence = event.event_sequence if event.event_sequence is not None else 2**63 - 1
    return sequence, str(event.event_id)


assert isinstance(MemoryMetadataStore(), MetadataStore)
assert isinstance(MemoryUnitOfWork(MemoryMetadataStore()), UnitOfWork)


__all__ = ["MemoryMetadataStore", "MemoryUnitOfWork"]
