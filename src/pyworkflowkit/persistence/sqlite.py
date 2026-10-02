"""Durable SQLite implementation of the canonical V2 MetadataStore."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from sqlalchemy import URL, Engine, create_engine, event, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from pyworkflowkit.errors import (
    DuplicateMetadataError,
    MetadataConflictError,
    MetadataInvariantError,
    MetadataNotFoundError,
)
from pyworkflowkit.migrations import current_revision, upgrade_database
from pyworkflowkit.persistence._sqlalchemy import models
from pyworkflowkit.persistence._sqlalchemy.base import DB_SCHEMA
from pyworkflowkit.persistence._sqlalchemy.mapping import (
    attempt_from_row,
    attempt_to_row,
    external_ref_from_row,
    external_ref_to_row,
    failure_to_json,
    manifest_from_row,
    task_run_from_row,
    task_run_to_row,
    transition_from_row,
    workflow_from_row,
    workflow_to_row,
)
from pyworkflowkit.persistence.contracts import (
    V2_METADATA_STORE_CONTRACT_VERSION,
    ManifestReference,
    MetadataStore,
    MetadataStoreMetadata,
    StateEntityType,
    StateTransitionRecord,
)
from pyworkflowkit.runtime.entities import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId
from pyworkflowkit.runtime.references import ExternalRunRef
from pyworkflowkit.states import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus
from pyworkflowkit.states.enums import WORKFLOW_TERMINAL_STATUSES

DEFAULT_V2_SQLITE_PATH = Path(".pyworkflow/state/pyworkflow-v2.sqlite3")


@dataclass(frozen=True, slots=True)
class SQLiteSettings:
    """Local durable V2 persistence settings."""

    path: Path = DEFAULT_V2_SQLITE_PATH
    busy_timeout_ms: int = 5_000
    wal: bool = True

    def __post_init__(self) -> None:
        if self.busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must be non-negative")


def _create_sqlite_engine(settings: SQLiteSettings) -> Engine:
    database_path = settings.path.expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        URL.create("sqlite+pysqlite", database=str(database_path)),
        execution_options={"schema_translate_map": {DB_SCHEMA: None}},
    )

    @event.listens_for(engine, "connect")
    def _configure_connection(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute(f"PRAGMA busy_timeout = {settings.busy_timeout_ms}")
            if settings.wal:
                cursor.execute("PRAGMA journal_mode = WAL")
        finally:
            cursor.close()

    return engine


class SQLiteMetadataStore:
    """Durable single-machine V2 MetadataStore backed by SQLite."""

    def __init__(
        self,
        path: str | Path = DEFAULT_V2_SQLITE_PATH,
        *,
        busy_timeout_ms: int = 5_000,
        wal: bool = True,
        create_schema: bool = True,
    ) -> None:
        self.settings = SQLiteSettings(
            path=Path(path),
            busy_timeout_ms=busy_timeout_ms,
            wal=wal,
        )
        self.engine = _create_sqlite_engine(self.settings)
        if create_schema:
            upgrade_database(self.engine)

        self._session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            expire_on_commit=False,
        )

    def metadata(self) -> MetadataStoreMetadata:
        revision = current_revision(self.engine)
        return MetadataStoreMetadata(
            contract_version=V2_METADATA_STORE_CONTRACT_VERSION,
            schema_version=revision or "unversioned",
            durable=True,
            supports_concurrent_writers=True,
            supports_atomic_batch=False,
        )

    def create_workflow_run(self, run: WorkflowRun) -> None:
        _require_initial_status(
            "WorkflowRun",
            str(run.run_id),
            run.status,
            WorkflowRunStatus.PENDING,
        )
        with self._session_factory.begin() as session:
            if session.get(models.WorkflowRunRow, str(run.run_id)) is not None:
                raise DuplicateMetadataError(
                    entity_type="WorkflowRun",
                    entity_id=str(run.run_id),
                )
            session.add(workflow_to_row(run))
            self._append_transition(
                session,
                StateEntityType.WORKFLOW_RUN,
                str(run.run_id),
                None,
                run.status.value,
                run.created_at,
            )

    def get_workflow_run(self, run_id: WorkflowRunId) -> WorkflowRun:
        with self._session_factory() as session:
            row = session.get(models.WorkflowRunRow, str(run_id))
            if row is None:
                raise MetadataNotFoundError(
                    entity_type="WorkflowRun",
                    entity_id=str(run_id),
                )
            return workflow_from_row(row)

    def update_workflow_run(
        self,
        run: WorkflowRun,
        *,
        expected_status: WorkflowRunStatus,
        transitioned_at: datetime | None = None,
    ) -> None:
        with self._session_factory.begin() as session:
            row = self._workflow_row(session, run.run_id)
            current = workflow_from_row(row)
            _require_status(
                entity_type="WorkflowRun",
                entity_id=str(run.run_id),
                actual=current.status,
                expected=expected_status,
            )
            _require_workflow_identity(current, run)
            _require_transition_timestamp(
                current.status.value,
                run.status.value,
                transitioned_at,
            )

            result = session.execute(
                update(models.WorkflowRunRow)
                .where(
                    models.WorkflowRunRow.run_id == str(run.run_id),
                    models.WorkflowRunRow.status == expected_status.value,
                )
                .values(
                    status=run.status.value,
                    started_at=run.started_at,
                    ended_at=run.ended_at,
                    failure_json=failure_to_json(run.failure),
                )
            )
            if result.rowcount != 1:
                self._raise_workflow_conflict(session, run.run_id, expected_status)

            if current.status is not run.status:
                self._append_transition(
                    session,
                    StateEntityType.WORKFLOW_RUN,
                    str(run.run_id),
                    current.status.value,
                    run.status.value,
                    transitioned_at,
                )

    def list_workflow_runs(self) -> tuple[WorkflowRun, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(models.WorkflowRunRow).order_by(models.WorkflowRunRow.run_id)
            ).all()
            return tuple(workflow_from_row(row) for row in rows)

    def list_unfinished_workflow_runs(self) -> tuple[WorkflowRun, ...]:
        terminal = tuple(status.value for status in WORKFLOW_TERMINAL_STATUSES)
        with self._session_factory() as session:
            rows = session.scalars(
                select(models.WorkflowRunRow)
                .where(models.WorkflowRunRow.status.not_in(terminal))
                .order_by(models.WorkflowRunRow.run_id)
            ).all()
            return tuple(workflow_from_row(row) for row in rows)

    def create_task_run(self, task_run: TaskRun) -> None:
        _require_initial_status(
            "TaskRun",
            str(task_run.task_run_id),
            task_run.status,
            TaskRunStatus.PENDING,
        )
        with self._session_factory.begin() as session:
            if session.get(models.TaskRunRow, str(task_run.task_run_id)) is not None:
                raise DuplicateMetadataError(
                    entity_type="TaskRun",
                    entity_id=str(task_run.task_run_id),
                )
            if (
                session.get(models.WorkflowRunRow, str(task_run.workflow_run_id))
                is None
            ):
                raise MetadataNotFoundError(
                    entity_type="WorkflowRun",
                    entity_id=str(task_run.workflow_run_id),
                )

            session.add(task_run_to_row(task_run))
            self._append_transition(
                session,
                StateEntityType.TASK_RUN,
                str(task_run.task_run_id),
                None,
                task_run.status.value,
                task_run.created_at,
            )

    def get_task_run(self, task_run_id: TaskRunId) -> TaskRun:
        with self._session_factory() as session:
            row = session.get(models.TaskRunRow, str(task_run_id))
            if row is None:
                raise MetadataNotFoundError(
                    entity_type="TaskRun",
                    entity_id=str(task_run_id),
                )
            return task_run_from_row(row)

    def update_task_run(
        self,
        task_run: TaskRun,
        *,
        expected_status: TaskRunStatus,
        transitioned_at: datetime | None = None,
    ) -> None:
        with self._session_factory.begin() as session:
            row = self._task_row(session, task_run.task_run_id)
            current = task_run_from_row(row)
            _require_status(
                entity_type="TaskRun",
                entity_id=str(task_run.task_run_id),
                actual=current.status,
                expected=expected_status,
            )
            _require_task_run_identity(current, task_run)
            _require_transition_timestamp(
                current.status.value,
                task_run.status.value,
                transitioned_at,
            )

            result = session.execute(
                update(models.TaskRunRow)
                .where(
                    models.TaskRunRow.task_run_id == str(task_run.task_run_id),
                    models.TaskRunRow.status == expected_status.value,
                )
                .values(
                    status=task_run.status.value,
                    started_at=task_run.started_at,
                    ended_at=task_run.ended_at,
                    skip_reason=(
                        task_run.skip_reason.value
                        if task_run.skip_reason is not None
                        else None
                    ),
                    block_reason=(
                        task_run.block_reason.value
                        if task_run.block_reason is not None
                        else None
                    ),
                    failure_json=failure_to_json(task_run.failure),
                )
            )
            if result.rowcount != 1:
                self._raise_task_conflict(
                    session,
                    task_run.task_run_id,
                    expected_status,
                )

            if current.status is not task_run.status:
                self._append_transition(
                    session,
                    StateEntityType.TASK_RUN,
                    str(task_run.task_run_id),
                    current.status.value,
                    task_run.status.value,
                    transitioned_at,
                )

    def list_task_runs(self, workflow_run_id: WorkflowRunId) -> tuple[TaskRun, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(models.TaskRunRow)
                .where(models.TaskRunRow.workflow_run_id == str(workflow_run_id))
                .order_by(models.TaskRunRow.task_key, models.TaskRunRow.task_run_id)
            ).all()
            return tuple(task_run_from_row(row) for row in rows)

    def append_task_attempt(self, attempt: TaskAttempt) -> None:
        _require_initial_status(
            "TaskAttempt",
            str(attempt.attempt_id),
            attempt.status,
            TaskAttemptStatus.PENDING,
        )
        with self._session_factory.begin() as session:
            if session.get(models.TaskAttemptRow, str(attempt.attempt_id)) is not None:
                raise DuplicateMetadataError(
                    entity_type="TaskAttempt",
                    entity_id=str(attempt.attempt_id),
                )
            if session.get(models.TaskRunRow, str(attempt.task_run_id)) is None:
                raise MetadataNotFoundError(
                    entity_type="TaskRun",
                    entity_id=str(attempt.task_run_id),
                )

            last_number = session.scalar(
                select(func.max(models.TaskAttemptRow.attempt_number)).where(
                    models.TaskAttemptRow.task_run_id == str(attempt.task_run_id)
                )
            )
            expected_number = 1 if last_number is None else int(last_number) + 1
            if attempt.attempt_number != expected_number:
                raise MetadataInvariantError(
                    reason=(
                        f"TaskAttempt {attempt.attempt_id} must use attempt_number "
                        f"{expected_number}, got {attempt.attempt_number}"
                    )
                )

            session.add(attempt_to_row(attempt))
            self._append_transition(
                session,
                StateEntityType.TASK_ATTEMPT,
                str(attempt.attempt_id),
                None,
                attempt.status.value,
                attempt.created_at,
            )

    def get_task_attempt(self, attempt_id: TaskAttemptId) -> TaskAttempt:
        with self._session_factory() as session:
            row = session.get(models.TaskAttemptRow, str(attempt_id))
            if row is None:
                raise MetadataNotFoundError(
                    entity_type="TaskAttempt",
                    entity_id=str(attempt_id),
                )
            return attempt_from_row(row)

    def update_task_attempt(
        self,
        attempt: TaskAttempt,
        *,
        expected_status: TaskAttemptStatus,
        transitioned_at: datetime | None = None,
    ) -> None:
        with self._session_factory.begin() as session:
            row = self._attempt_row(session, attempt.attempt_id)
            current = attempt_from_row(row)
            _require_status(
                entity_type="TaskAttempt",
                entity_id=str(attempt.attempt_id),
                actual=current.status,
                expected=expected_status,
            )
            _require_attempt_identity(current, attempt)
            _require_transition_timestamp(
                current.status.value,
                attempt.status.value,
                transitioned_at,
            )

            result = session.execute(
                update(models.TaskAttemptRow)
                .where(
                    models.TaskAttemptRow.attempt_id == str(attempt.attempt_id),
                    models.TaskAttemptRow.status == expected_status.value,
                )
                .values(
                    status=attempt.status.value,
                    started_at=attempt.started_at,
                    ended_at=attempt.ended_at,
                    failure_json=failure_to_json(attempt.failure),
                )
            )
            if result.rowcount != 1:
                self._raise_attempt_conflict(
                    session,
                    attempt.attempt_id,
                    expected_status,
                )

            if current.status is not attempt.status:
                self._append_transition(
                    session,
                    StateEntityType.TASK_ATTEMPT,
                    str(attempt.attempt_id),
                    current.status.value,
                    attempt.status.value,
                    transitioned_at,
                )

    def list_task_attempts(self, task_run_id: TaskRunId) -> tuple[TaskAttempt, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(models.TaskAttemptRow)
                .where(models.TaskAttemptRow.task_run_id == str(task_run_id))
                .order_by(models.TaskAttemptRow.attempt_number)
            ).all()
            return tuple(attempt_from_row(row) for row in rows)

    def append_external_run_ref(
        self,
        *,
        attempt_id: TaskAttemptId,
        external_ref: ExternalRunRef,
    ) -> None:
        if not isinstance(external_ref, ExternalRunRef):
            raise TypeError("external_ref must be an ExternalRunRef")

        with self._session_factory.begin() as session:
            if session.get(models.TaskAttemptRow, str(attempt_id)) is None:
                raise MetadataNotFoundError(
                    entity_type="TaskAttempt",
                    entity_id=str(attempt_id),
                )
            duplicate = session.scalar(
                select(models.ExternalRunRefRow.external_ref_pk).where(
                    models.ExternalRunRefRow.attempt_id == str(attempt_id),
                    models.ExternalRunRefRow.provider == external_ref.provider,
                    models.ExternalRunRefRow.kind == external_ref.kind,
                    models.ExternalRunRefRow.external_run_id
                    == external_ref.external_run_id,
                )
            )
            if duplicate is not None:
                raise DuplicateMetadataError(
                    entity_type="ExternalRunRef",
                    entity_id=(
                        f"{attempt_id}:{external_ref.provider}:"
                        f"{external_ref.kind}:{external_ref.external_run_id}"
                    ),
                )

            session.add(
                external_ref_to_row(
                    attempt_id=attempt_id,
                    value=external_ref,
                )
            )

    def list_external_run_refs(
        self,
        attempt_id: TaskAttemptId,
    ) -> tuple[ExternalRunRef, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(models.ExternalRunRefRow)
                .where(models.ExternalRunRefRow.attempt_id == str(attempt_id))
                .order_by(
                    models.ExternalRunRefRow.provider,
                    models.ExternalRunRefRow.kind,
                    models.ExternalRunRefRow.external_run_id,
                )
            ).all()
            return tuple(external_ref_from_row(row) for row in rows)

    def list_state_transitions(
        self,
        *,
        entity_type: StateEntityType | None = None,
        entity_id: str | None = None,
    ) -> tuple[StateTransitionRecord, ...]:
        statement = select(models.StateTransitionRow)
        if entity_type is not None:
            if not isinstance(entity_type, StateEntityType):
                raise TypeError("entity_type must be a StateEntityType or None")
            statement = statement.where(
                models.StateTransitionRow.entity_type == entity_type.value
            )
        if entity_id is not None:
            if not isinstance(entity_id, str):
                raise TypeError("entity_id must be a string or None")
            if not entity_id.strip():
                raise ValueError("entity_id must not be empty when provided")
            statement = statement.where(models.StateTransitionRow.entity_id == entity_id)

        with self._session_factory() as session:
            rows = session.scalars(
                statement.order_by(models.StateTransitionRow.sequence)
            ).all()
            return tuple(transition_from_row(row) for row in rows)

    def set_manifest_reference(
        self,
        run_id: WorkflowRunId,
        reference: ManifestReference,
    ) -> None:
        if not isinstance(reference, ManifestReference):
            raise TypeError("reference must be a ManifestReference")

        with self._session_factory.begin() as session:
            if session.get(models.WorkflowRunRow, str(run_id)) is None:
                raise MetadataNotFoundError(
                    entity_type="WorkflowRun",
                    entity_id=str(run_id),
                )
            existing = session.get(models.ManifestReferenceRow, str(run_id))
            if existing is not None:
                current = manifest_from_row(existing)
                if current != reference:
                    raise MetadataConflictError(
                        entity_type="ManifestReference",
                        entity_id=str(run_id),
                        expected="unchanged or absent",
                        actual="different persisted reference",
                    )
                return

            session.add(
                models.ManifestReferenceRow(
                    workflow_run_id=str(run_id),
                    locator=reference.locator,
                    schema_version=reference.schema_version,
                    digest=reference.digest,
                )
            )

    def get_manifest_reference(self, run_id: WorkflowRunId) -> ManifestReference:
        with self._session_factory() as session:
            row = session.get(models.ManifestReferenceRow, str(run_id))
            if row is None:
                raise MetadataNotFoundError(
                    entity_type="ManifestReference",
                    entity_id=str(run_id),
                )
            return manifest_from_row(row)

    def close(self) -> None:
        self.engine.dispose()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()

    @staticmethod
    def _append_transition(
        session: Session,
        entity_type: StateEntityType,
        entity_id: str,
        from_status: str | None,
        to_status: str,
        occurred_at: datetime | None,
    ) -> None:
        if occurred_at is None:
            raise MetadataInvariantError(
                reason="state transition evidence requires occurred_at"
            )
        session.add(
            models.StateTransitionRow(
                entity_type=entity_type.value,
                entity_id=entity_id,
                from_status=from_status,
                to_status=to_status,
                occurred_at=occurred_at,
            )
        )

    @staticmethod
    def _workflow_row(session: Session, run_id: WorkflowRunId) -> models.WorkflowRunRow:
        row = session.get(models.WorkflowRunRow, str(run_id))
        if row is None:
            raise MetadataNotFoundError(
                entity_type="WorkflowRun",
                entity_id=str(run_id),
            )
        return row

    @staticmethod
    def _task_row(session: Session, task_run_id: TaskRunId) -> models.TaskRunRow:
        row = session.get(models.TaskRunRow, str(task_run_id))
        if row is None:
            raise MetadataNotFoundError(
                entity_type="TaskRun",
                entity_id=str(task_run_id),
            )
        return row

    @staticmethod
    def _attempt_row(
        session: Session,
        attempt_id: TaskAttemptId,
    ) -> models.TaskAttemptRow:
        row = session.get(models.TaskAttemptRow, str(attempt_id))
        if row is None:
            raise MetadataNotFoundError(
                entity_type="TaskAttempt",
                entity_id=str(attempt_id),
            )
        return row

    @staticmethod
    def _raise_workflow_conflict(
        session: Session,
        run_id: WorkflowRunId,
        expected: WorkflowRunStatus,
    ) -> None:
        actual = session.scalar(
            select(models.WorkflowRunRow.status).where(
                models.WorkflowRunRow.run_id == str(run_id)
            )
        )
        raise MetadataConflictError(
            entity_type="WorkflowRun",
            entity_id=str(run_id),
            expected=expected.value,
            actual=str(actual or "<missing>"),
        )

    @staticmethod
    def _raise_task_conflict(
        session: Session,
        task_run_id: TaskRunId,
        expected: TaskRunStatus,
    ) -> None:
        actual = session.scalar(
            select(models.TaskRunRow.status).where(
                models.TaskRunRow.task_run_id == str(task_run_id)
            )
        )
        raise MetadataConflictError(
            entity_type="TaskRun",
            entity_id=str(task_run_id),
            expected=expected.value,
            actual=str(actual or "<missing>"),
        )

    @staticmethod
    def _raise_attempt_conflict(
        session: Session,
        attempt_id: TaskAttemptId,
        expected: TaskAttemptStatus,
    ) -> None:
        actual = session.scalar(
            select(models.TaskAttemptRow.status).where(
                models.TaskAttemptRow.attempt_id == str(attempt_id)
            )
        )
        raise MetadataConflictError(
            entity_type="TaskAttempt",
            entity_id=str(attempt_id),
            expected=expected.value,
            actual=str(actual or "<missing>"),
        )


def _require_initial_status(
    entity_type: str,
    entity_id: str,
    actual: WorkflowRunStatus | TaskRunStatus | TaskAttemptStatus,
    expected: WorkflowRunStatus | TaskRunStatus | TaskAttemptStatus,
) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise MetadataInvariantError(
            reason=(
                f"new {entity_type} {entity_id} must begin in {expected.value}; "
                f"got {actual.value}"
            )
        )


def _require_status(
    *,
    entity_type: str,
    entity_id: str,
    actual: WorkflowRunStatus | TaskRunStatus | TaskAttemptStatus,
    expected: WorkflowRunStatus | TaskRunStatus | TaskAttemptStatus,
) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise MetadataConflictError(
            entity_type=entity_type,
            entity_id=entity_id,
            expected=expected.value,
            actual=actual.value,
        )


def _require_workflow_identity(current: WorkflowRun, candidate: WorkflowRun) -> None:
    stable = (
        current.run_id == candidate.run_id
        and current.workflow_name == candidate.workflow_name
        and current.workflow_version == candidate.workflow_version
        and current.definition_fingerprint == candidate.definition_fingerprint
        and current.plan_fingerprint == candidate.plan_fingerprint
        and current.correlation == candidate.correlation
        and current.created_at == candidate.created_at
    )
    if not stable:
        raise MetadataInvariantError(
            reason="WorkflowRun immutable identity fields changed"
        )


def _require_task_run_identity(current: TaskRun, candidate: TaskRun) -> None:
    stable = (
        current.task_run_id == candidate.task_run_id
        and current.workflow_run_id == candidate.workflow_run_id
        and current.task_key == candidate.task_key
        and current.created_at == candidate.created_at
    )
    if not stable:
        raise MetadataInvariantError(reason="TaskRun immutable identity fields changed")


def _require_attempt_identity(current: TaskAttempt, candidate: TaskAttempt) -> None:
    stable = (
        current.attempt_id == candidate.attempt_id
        and current.task_run_id == candidate.task_run_id
        and current.attempt_number == candidate.attempt_number
        and current.created_at == candidate.created_at
    )
    if not stable:
        raise MetadataInvariantError(
            reason="TaskAttempt immutable identity fields changed"
        )


def _require_transition_timestamp(
    current_status: str,
    candidate_status: str,
    transitioned_at: datetime | None,
) -> None:
    if current_status != candidate_status and transitioned_at is None:
        raise MetadataInvariantError(
            reason="status-changing update requires transitioned_at"
        )


if not isinstance(SQLiteMetadataStore, type):
    raise TypeError("SQLiteMetadataStore must be a concrete type")


__all__ = [
    "DEFAULT_V2_SQLITE_PATH",
    "SQLiteMetadataStore",
    "SQLiteSettings",
]
