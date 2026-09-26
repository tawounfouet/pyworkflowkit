"""Dialect-neutral SQLAlchemy implementation of MetadataStore."""

from types import TracebackType
from typing import Self

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from pyworkflowkit.adapters.metadata.sqlalchemy import models as orm_models
from pyworkflowkit.adapters.metadata.sqlalchemy.mapping import SqlAlchemyRowMapper
from pyworkflowkit.adapters.persistence.mapping import PersistenceMapper
from pyworkflowkit.domain.ids import TaskRunId, WorkflowRunId
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef
from pyworkflowkit.errors import (
    DuplicateMetadataError,
    MetadataNotFoundError,
    MetadataStoreError,
    UnitOfWorkStateError,
)
from pyworkflowkit.ports.metadata_store import UnitOfWork


class SqlAlchemyMetadataStore:
    """MetadataStore backed by an injected SQLAlchemy Session factory."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def unit_of_work(self) -> UnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)

    def get_workflow_run(self, run_id: WorkflowRunId) -> WorkflowRun:
        with self._session_factory() as session:
            row = session.get(orm_models.WorkflowRunRow, str(run_id))
            if row is None:
                raise MetadataNotFoundError(entity_type="WorkflowRun", entity_id=str(run_id))
            return PersistenceMapper.workflow_run_from_row(
                SqlAlchemyRowMapper.workflow_run_from_orm(row)
            )

    def get_task_run(self, task_run_id: TaskRunId) -> TaskRun:
        with self._session_factory() as session:
            row = session.get(orm_models.TaskRunRow, str(task_run_id))
            if row is None:
                raise MetadataNotFoundError(entity_type="TaskRun", entity_id=str(task_run_id))
            return PersistenceMapper.task_run_from_row(SqlAlchemyRowMapper.task_run_from_orm(row))

    def list_task_runs(self, run_id: WorkflowRunId) -> tuple[TaskRun, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(orm_models.TaskRunRow).where(orm_models.TaskRunRow.run_id == str(run_id))
            ).all()
        values = (
            PersistenceMapper.task_run_from_row(SqlAlchemyRowMapper.task_run_from_orm(row))
            for row in rows
        )
        return tuple(sorted(values, key=lambda value: str(value.task_id)))

    def list_task_attempts(self, task_run_id: TaskRunId) -> tuple[TaskAttempt, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(orm_models.TaskAttemptRow).where(
                    orm_models.TaskAttemptRow.task_run_id == str(task_run_id)
                )
            ).all()
        values = (
            PersistenceMapper.task_attempt_from_row(
                SqlAlchemyRowMapper.task_attempt_from_orm(row)
            )
            for row in rows
        )
        return tuple(sorted(values, key=lambda value: value.attempt_number))

    def list_events(self, run_id: WorkflowRunId) -> tuple[RuntimeEvent, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(orm_models.RuntimeEventRow).where(
                    orm_models.RuntimeEventRow.run_id == str(run_id)
                )
            ).all()
        values = (
            PersistenceMapper.runtime_event_from_row(
                SqlAlchemyRowMapper.runtime_event_from_orm(row)
            )
            for row in rows
        )
        return tuple(sorted(values, key=_event_sort_key))

    def list_artifacts(self, task_run_id: TaskRunId) -> tuple[ArtifactReference, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(orm_models.ArtifactReferenceRow).where(
                    orm_models.ArtifactReferenceRow.task_run_id == str(task_run_id)
                )
            ).all()
        values = []
        for row in rows:
            _, artifact = PersistenceMapper.artifact_from_row(
                SqlAlchemyRowMapper.artifact_from_orm(row)
            )
            values.append(artifact)
        return tuple(sorted(values, key=lambda value: str(value.artifact_id)))

    def list_external_run_refs(
        self,
        task_run_id: TaskRunId,
    ) -> tuple[ExternalRunRef, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(orm_models.ExternalRunRefRow).where(
                    orm_models.ExternalRunRefRow.task_run_id == str(task_run_id)
                )
            ).all()
        values = []
        for row in rows:
            _, external_ref = PersistenceMapper.external_ref_from_row(
                SqlAlchemyRowMapper.external_ref_from_orm(row)
            )
            values.append(external_ref)
        return tuple(sorted(values, key=lambda value: str(value.external_ref_id)))


class SqlAlchemyUnitOfWork:
    """Explicit SQLAlchemy transaction boundary matching the UnitOfWork port."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None
        self._active = False

    def __enter__(self) -> Self:
        if self._active:
            raise UnitOfWorkStateError(reason="unit of work is already active")
        self._session = self._session_factory()
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
        session = self._require_session()
        record = PersistenceMapper.workflow_run_to_row(run)
        if session.get(orm_models.WorkflowRunRow, record.run_id) is not None:
            raise DuplicateMetadataError(entity_type="WorkflowRun", entity_id=record.run_id)
        session.add(SqlAlchemyRowMapper.workflow_run_to_orm(record))
        self._flush()

    def save_workflow_run(self, run: WorkflowRun) -> None:
        session = self._require_session()
        record = PersistenceMapper.workflow_run_to_row(run)
        target = session.get(orm_models.WorkflowRunRow, record.run_id)
        if target is None:
            raise MetadataNotFoundError(entity_type="WorkflowRun", entity_id=record.run_id)
        SqlAlchemyRowMapper.apply_workflow_run(target, record)
        self._flush()

    def add_task_run(self, task_run: TaskRun) -> None:
        session = self._require_session()
        record = PersistenceMapper.task_run_to_row(task_run)
        if session.get(orm_models.TaskRunRow, record.task_run_id) is not None:
            raise DuplicateMetadataError(entity_type="TaskRun", entity_id=record.task_run_id)
        if session.get(orm_models.WorkflowRunRow, record.run_id) is None:
            raise MetadataNotFoundError(entity_type="WorkflowRun", entity_id=record.run_id)
        session.add(SqlAlchemyRowMapper.task_run_to_orm(record))
        self._flush()

    def save_task_run(self, task_run: TaskRun) -> None:
        session = self._require_session()
        record = PersistenceMapper.task_run_to_row(task_run)
        target = session.get(orm_models.TaskRunRow, record.task_run_id)
        if target is None:
            raise MetadataNotFoundError(entity_type="TaskRun", entity_id=record.task_run_id)
        SqlAlchemyRowMapper.apply_task_run(target, record)
        self._flush()

    def add_task_attempt(self, attempt: TaskAttempt) -> None:
        session = self._require_session()
        record = PersistenceMapper.task_attempt_to_row(attempt)
        if session.get(orm_models.TaskAttemptRow, record.attempt_id) is not None:
            raise DuplicateMetadataError(entity_type="TaskAttempt", entity_id=record.attempt_id)
        if session.get(orm_models.TaskRunRow, record.task_run_id) is None:
            raise MetadataNotFoundError(entity_type="TaskRun", entity_id=record.task_run_id)
        duplicate = session.scalar(
            select(orm_models.TaskAttemptRow).where(
                orm_models.TaskAttemptRow.task_run_id == record.task_run_id,
                orm_models.TaskAttemptRow.attempt_number == record.attempt_number,
            )
        )
        if duplicate is not None:
            raise DuplicateMetadataError(
                entity_type="TaskAttemptNumber",
                entity_id=f"{record.task_run_id}:{record.attempt_number}",
            )
        session.add(SqlAlchemyRowMapper.task_attempt_to_orm(record))
        self._flush()

    def save_task_attempt(self, attempt: TaskAttempt) -> None:
        session = self._require_session()
        record = PersistenceMapper.task_attempt_to_row(attempt)
        target = session.get(orm_models.TaskAttemptRow, record.attempt_id)
        if target is None:
            raise MetadataNotFoundError(entity_type="TaskAttempt", entity_id=record.attempt_id)
        SqlAlchemyRowMapper.apply_task_attempt(target, record)
        self._flush()

    def add_event(self, event: RuntimeEvent) -> None:
        session = self._require_session()
        record = PersistenceMapper.runtime_event_to_row(event)
        if session.get(orm_models.RuntimeEventRow, record.event_id) is not None:
            raise DuplicateMetadataError(entity_type="RuntimeEvent", entity_id=record.event_id)
        if session.get(orm_models.WorkflowRunRow, record.run_id) is None:
            raise MetadataNotFoundError(entity_type="WorkflowRun", entity_id=record.run_id)
        if record.task_run_id is not None and session.get(
            orm_models.TaskRunRow, record.task_run_id
        ) is None:
            raise MetadataNotFoundError(entity_type="TaskRun", entity_id=record.task_run_id)
        if record.event_sequence is not None:
            duplicate = session.scalar(
                select(orm_models.RuntimeEventRow).where(
                    orm_models.RuntimeEventRow.run_id == record.run_id,
                    orm_models.RuntimeEventRow.event_sequence == record.event_sequence,
                )
            )
            if duplicate is not None:
                raise DuplicateMetadataError(
                    entity_type="RuntimeEventSequence",
                    entity_id=f"{record.run_id}:{record.event_sequence}",
                )
        session.add(SqlAlchemyRowMapper.runtime_event_to_orm(record))
        self._flush()

    def add_artifact(
        self,
        *,
        task_run_id: TaskRunId,
        artifact: ArtifactReference,
    ) -> None:
        session = self._require_session()
        if session.get(orm_models.TaskRunRow, str(task_run_id)) is None:
            raise MetadataNotFoundError(entity_type="TaskRun", entity_id=str(task_run_id))
        record = PersistenceMapper.artifact_to_row(task_run_id=task_run_id, value=artifact)
        if session.get(orm_models.ArtifactReferenceRow, record.artifact_id) is not None:
            raise DuplicateMetadataError(entity_type="Artifact", entity_id=record.artifact_id)
        session.add(SqlAlchemyRowMapper.artifact_to_orm(record))
        self._flush()

    def add_external_run_ref(
        self,
        *,
        task_run_id: TaskRunId,
        external_ref: ExternalRunRef,
    ) -> None:
        session = self._require_session()
        if session.get(orm_models.TaskRunRow, str(task_run_id)) is None:
            raise MetadataNotFoundError(entity_type="TaskRun", entity_id=str(task_run_id))
        record = PersistenceMapper.external_ref_to_row(
            task_run_id=task_run_id,
            value=external_ref,
        )
        if session.get(orm_models.ExternalRunRefRow, record.external_ref_id) is not None:
            raise DuplicateMetadataError(
                entity_type="ExternalRunRef",
                entity_id=record.external_ref_id,
            )
        session.add(SqlAlchemyRowMapper.external_ref_to_orm(record))
        self._flush()

    def commit(self) -> None:
        session = self._require_session()
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise DuplicateMetadataError(
                entity_type="RelationalConstraint",
                entity_id="commit",
            ) from exc
        except SQLAlchemyError as exc:
            session.rollback()
            raise MetadataStoreError("SQLAlchemy persistence commit failed.") from exc
        finally:
            session.close()
            self._session = None
            self._active = False

    def rollback(self) -> None:
        session = self._require_session()
        try:
            session.rollback()
        finally:
            session.close()
            self._session = None
            self._active = False

    def _flush(self) -> None:
        session = self._require_session()
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise DuplicateMetadataError(
                entity_type="RelationalConstraint",
                entity_id="flush",
            ) from exc
        except SQLAlchemyError as exc:
            session.rollback()
            raise MetadataStoreError("SQLAlchemy persistence flush failed.") from exc

    def _require_session(self) -> Session:
        if not self._active or self._session is None:
            raise UnitOfWorkStateError(reason="unit of work must be entered before use")
        return self._session


def _event_sort_key(event: RuntimeEvent) -> tuple[int, str]:
    sequence = event.event_sequence if event.event_sequence is not None else 2**63 - 1
    return sequence, str(event.event_id)


__all__ = ["SqlAlchemyMetadataStore", "SqlAlchemyUnitOfWork"]
