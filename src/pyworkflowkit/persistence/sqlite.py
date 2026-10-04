"""Durable SQLite implementation of the canonical V2 MetadataStore."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Any, Self, cast

from sqlalchemy import URL, Engine, create_engine, delete, event, func, or_, select, update
from sqlalchemy.engine import CursorResult
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
    output_checkpoint_from_row,
    output_checkpoint_to_row,
    task_run_from_row,
    task_run_to_row,
    transition_from_row,
    workflow_from_row,
    workflow_to_row,
)
from pyworkflowkit.persistence.contracts import (
    V2_METADATA_STORE_CONTRACT_VERSION,
    DeletedRecordsSummary,
    ManifestReference,
    MetadataStoreMetadata,
    PruneReport,
    RetentionPolicy,
    StateEntityType,
    StateTransitionRecord,
)
from pyworkflowkit.runtime.entities import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.runtime.evidence import (
    RuntimeEvent,
    TaskOutputCheckpoint,
    runtime_event_type_for_transition,
)
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
            if cast(CursorResult[Any], result).rowcount != 1:
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
            if session.get(models.WorkflowRunRow, str(task_run.workflow_run_id)) is None:
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

            db_status = (
                TaskRunStatus.SUCCEEDED.value
                if task_run.status is TaskRunStatus.REUSED
                else task_run.status.value
            )
            expected_db_status = (
                TaskRunStatus.SUCCEEDED.value
                if expected_status is TaskRunStatus.REUSED
                else expected_status.value
            )
            failure_payload = failure_to_json(task_run.failure)
            if task_run.status is TaskRunStatus.REUSED:
                if failure_payload is None:
                    failure_payload = {"__reused__": True}
                elif isinstance(failure_payload, dict):
                    failure_payload = dict(failure_payload)
                    failure_payload["__reused__"] = True

            result = session.execute(
                update(models.TaskRunRow)
                .where(
                    models.TaskRunRow.task_run_id == str(task_run.task_run_id),
                    models.TaskRunRow.status == expected_db_status,
                )
                .values(
                    status=db_status,
                    started_at=task_run.started_at,
                    ended_at=task_run.ended_at,
                    skip_reason=(
                        task_run.skip_reason.value if task_run.skip_reason is not None else None
                    ),
                    block_reason=(
                        task_run.block_reason.value if task_run.block_reason is not None else None
                    ),
                    failure_json=failure_payload,
                )
            )
            if cast(CursorResult[Any], result).rowcount != 1:
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
            if cast(CursorResult[Any], result).rowcount != 1:
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
                    models.ExternalRunRefRow.external_run_id == external_ref.external_run_id,
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
            statement = statement.where(models.StateTransitionRow.entity_type == entity_type.value)
        if entity_id is not None:
            if not isinstance(entity_id, str):
                raise TypeError("entity_id must be a string or None")
            if not entity_id.strip():
                raise ValueError("entity_id must not be empty when provided")
            statement = statement.where(models.StateTransitionRow.entity_id == entity_id)

        with self._session_factory() as session:
            rows = session.scalars(statement.order_by(models.StateTransitionRow.sequence)).all()
            return tuple(transition_from_row(row) for row in rows)

    def list_runtime_events(
        self,
        workflow_run_id: WorkflowRunId,
    ) -> tuple[RuntimeEvent, ...]:
        with self._session_factory() as session:
            workflow_row = session.get(models.WorkflowRunRow, str(workflow_run_id))
            if workflow_row is None:
                raise MetadataNotFoundError(
                    entity_type="WorkflowRun",
                    entity_id=str(workflow_run_id),
                )

            is_resume = bool(
                workflow_row.correlation_json
                and workflow_row.correlation_json.get("resume_of_run_id")
            )

            transitions = session.scalars(
                select(models.StateTransitionRow).order_by(models.StateTransitionRow.sequence)
            ).all()
            events: list[RuntimeEvent] = []
            for row in transitions:
                entity_type = StateEntityType(row.entity_type)
                task_run_id: TaskRunId | None = None
                attempt_id: TaskAttemptId | None = None
                task_key: str | None = None
                attempt_number: int | None = None

                if entity_type is StateEntityType.WORKFLOW_RUN:
                    if row.entity_id != str(workflow_run_id):
                        continue
                elif entity_type is StateEntityType.TASK_RUN:
                    task_row = session.get(models.TaskRunRow, row.entity_id)
                    if task_row is None or task_row.workflow_run_id != str(workflow_run_id):
                        continue
                    task_run_id = TaskRunId.parse(task_row.task_run_id)
                    task_key = task_row.task_key
                else:
                    attempt_row = session.get(models.TaskAttemptRow, row.entity_id)
                    if attempt_row is None:
                        continue
                    task_row = session.get(models.TaskRunRow, attempt_row.task_run_id)
                    if task_row is None or task_row.workflow_run_id != str(workflow_run_id):
                        continue
                    task_run_id = TaskRunId.parse(task_row.task_run_id)
                    attempt_id = TaskAttemptId.parse(attempt_row.attempt_id)
                    task_key = task_row.task_key
                    attempt_number = attempt_row.attempt_number

                event_type = runtime_event_type_for_transition(
                    entity_type=entity_type.value,
                    from_status=row.from_status,
                    to_status=row.to_status,
                    attempt_number=attempt_number,
                    is_resume=is_resume,
                )
                if event_type is None:
                    continue

                events.append(
                    RuntimeEvent(
                        sequence=row.sequence,
                        event_id=f"{workflow_run_id}:event-{row.sequence}",
                        event_type=event_type,
                        workflow_run_id=workflow_run_id,
                        task_run_id=task_run_id,
                        attempt_id=attempt_id,
                        task_key=task_key,
                        attempt_number=attempt_number,
                        occurred_at=row.occurred_at,
                        from_status=row.from_status,
                        to_status=row.to_status,
                        payload={
                            "entity_type": entity_type.value,
                            "entity_id": row.entity_id,
                        },
                    )
                )
            return tuple(events)

    def set_task_output_checkpoint(
        self,
        checkpoint: TaskOutputCheckpoint,
    ) -> None:
        if not isinstance(checkpoint, TaskOutputCheckpoint):
            raise TypeError("checkpoint must be a TaskOutputCheckpoint")
        with self._session_factory.begin() as session:
            task_row = session.get(models.TaskRunRow, str(checkpoint.task_run_id))
            if task_row is None:
                raise MetadataNotFoundError(
                    entity_type="TaskRun",
                    entity_id=str(checkpoint.task_run_id),
                )
            if task_row.status not in {
                TaskRunStatus.SUCCEEDED.value,
                TaskRunStatus.REUSED.value,
            }:
                raise MetadataInvariantError(
                    reason="TaskOutputCheckpoint requires a SUCCEEDED or REUSED TaskRun"
                )
            existing = session.get(
                models.TaskOutputCheckpointRow,
                str(checkpoint.task_run_id),
            )
            if existing is not None:
                current = output_checkpoint_from_row(existing)
                if current != checkpoint:
                    raise MetadataConflictError(
                        entity_type="TaskOutputCheckpoint",
                        entity_id=str(checkpoint.task_run_id),
                        expected="unchanged or absent",
                        actual="different persisted checkpoint",
                    )
                return
            session.add(output_checkpoint_to_row(checkpoint))

    def get_task_output_checkpoint(
        self,
        task_run_id: TaskRunId,
    ) -> TaskOutputCheckpoint:
        with self._session_factory() as session:
            row = session.get(models.TaskOutputCheckpointRow, str(task_run_id))
            if row is None:
                raise MetadataNotFoundError(
                    entity_type="TaskOutputCheckpoint",
                    entity_id=str(task_run_id),
                )
            return output_checkpoint_from_row(row)

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

    def prune_runs(
        self,
        policy: RetentionPolicy,
        *,
        dry_run: bool = False,
        batch_size: int = 500,
        now: datetime | None = None,
    ) -> PruneReport:
        if not isinstance(policy, RetentionPolicy):
            raise TypeError("policy must be a RetentionPolicy")
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")

        reference_now = now or datetime.now(UTC)
        if reference_now.tzinfo is None:
            reference_now = reference_now.replace(tzinfo=UTC)

        with self._session_factory() as session:
            stmt = select(models.WorkflowRunRow.workflow_name).distinct()
            if policy.workflow_names:
                stmt = stmt.where(models.WorkflowRunRow.workflow_name.in_(policy.workflow_names))
            workflow_names = sorted(list(session.scalars(stmt).all()))
            scanned_workflows = len(workflow_names)

            eligible_run_ids: list[str] = []

            for wf_name in workflow_names:
                wf_runs = session.scalars(
                    select(models.WorkflowRunRow)
                    .where(models.WorkflowRunRow.workflow_name == wf_name)
                    .order_by(
                        models.WorkflowRunRow.created_at.desc(),
                        models.WorkflowRunRow.run_id.asc(),
                    )
                ).all()

                for rank, run_row in enumerate(wf_runs, start=1):
                    if run_row.status not in {s.value for s in WORKFLOW_TERMINAL_STATUSES}:
                        continue
                    if run_row.status not in {s.value for s in policy.prune_states}:
                        continue

                    is_failed = run_row.status == WorkflowRunStatus.FAILED.value
                    cutoff_days = (
                        policy.retain_failed_runs_days
                        if is_failed and policy.retain_failed_runs_days is not None
                        else policy.retention_days
                    )
                    age_eligible = False
                    if cutoff_days is not None:
                        cutoff_date = reference_now - timedelta(days=cutoff_days)
                        created_dt = run_row.created_at
                        if created_dt.tzinfo is None:
                            created_dt = created_dt.replace(tzinfo=UTC)
                        age_eligible = created_dt < cutoff_date

                    quota_eligible = False
                    if policy.max_runs_per_workflow is not None:
                        quota_eligible = rank > policy.max_runs_per_workflow

                    if age_eligible or quota_eligible:
                        eligible_run_ids.append(run_row.run_id)

            if not eligible_run_ids:
                return PruneReport(
                    dry_run=dry_run,
                    scanned_workflows=scanned_workflows,
                    eligible_runs_to_prune=0,
                    deleted_records=DeletedRecordsSummary(),
                )

            if dry_run:
                task_run_ids = list(
                    session.scalars(
                        select(models.TaskRunRow.task_run_id).where(
                            models.TaskRunRow.workflow_run_id.in_(eligible_run_ids)
                        )
                    ).all()
                )

                attempt_ids: list[str] = []
                if task_run_ids:
                    attempt_ids = list(
                        session.scalars(
                            select(models.TaskAttemptRow.attempt_id).where(
                                models.TaskAttemptRow.task_run_id.in_(task_run_ids)
                            )
                        ).all()
                    )

                checkpoint_count = 0
                if task_run_ids:
                    checkpoint_count = (
                        session.scalar(
                            select(func.count())
                            .select_from(models.TaskOutputCheckpointRow)
                            .where(models.TaskOutputCheckpointRow.task_run_id.in_(task_run_ids))
                        )
                        or 0
                    )

                external_refs_count = 0
                if attempt_ids:
                    external_refs_count = (
                        session.scalar(
                            select(func.count())
                            .select_from(models.ExternalRunRefRow)
                            .where(models.ExternalRunRefRow.attempt_id.in_(attempt_ids))
                        )
                        or 0
                    )

                manifest_count = (
                    session.scalar(
                        select(func.count())
                        .select_from(models.ManifestReferenceRow)
                        .where(models.ManifestReferenceRow.workflow_run_id.in_(eligible_run_ids))
                    )
                    or 0
                )

                wf_type = StateEntityType.WORKFLOW_RUN.value
                task_type = StateEntityType.TASK_RUN.value
                att_type = StateEntityType.TASK_ATTEMPT.value

                trans_conds = [
                    (models.StateTransitionRow.entity_type == wf_type)
                    & models.StateTransitionRow.entity_id.in_(eligible_run_ids)
                ]
                if task_run_ids:
                    trans_conds.append(
                        (models.StateTransitionRow.entity_type == task_type)
                        & models.StateTransitionRow.entity_id.in_(task_run_ids)
                    )
                if attempt_ids:
                    trans_conds.append(
                        (models.StateTransitionRow.entity_type == att_type)
                        & models.StateTransitionRow.entity_id.in_(attempt_ids)
                    )

                transitions_count = (
                    session.scalar(
                        select(func.count())
                        .select_from(models.StateTransitionRow)
                        .where(or_(*trans_conds))
                    )
                    or 0
                )

                summary = DeletedRecordsSummary(
                    workflow_runs=len(eligible_run_ids),
                    task_runs=len(task_run_ids),
                    task_attempts=len(attempt_ids),
                    events=int(transitions_count),
                    checkpoints=int(checkpoint_count),
                    external_refs=int(external_refs_count),
                    manifests=int(manifest_count),
                )
                return PruneReport(
                    dry_run=True,
                    scanned_workflows=scanned_workflows,
                    eligible_runs_to_prune=len(eligible_run_ids),
                    deleted_records=summary,
                )

        total_summary = DeletedRecordsSummary()

        for i in range(0, len(eligible_run_ids), batch_size):
            batch_run_ids = eligible_run_ids[i : i + batch_size]
            with self._session_factory() as session, session.begin():
                task_run_ids = list(
                    session.scalars(
                        select(models.TaskRunRow.task_run_id).where(
                            models.TaskRunRow.workflow_run_id.in_(batch_run_ids)
                        )
                    ).all()
                )

                attempt_ids = []
                if task_run_ids:
                    attempt_ids = list(
                        session.scalars(
                            select(models.TaskAttemptRow.attempt_id).where(
                                models.TaskAttemptRow.task_run_id.in_(task_run_ids)
                            )
                        ).all()
                    )

                del_cp = 0
                if task_run_ids:
                    res_cp = session.execute(
                        delete(models.TaskOutputCheckpointRow).where(
                            models.TaskOutputCheckpointRow.task_run_id.in_(task_run_ids)
                        )
                    )
                    del_cp = int(cast(CursorResult[Any], res_cp).rowcount or 0)

                wf_type = StateEntityType.WORKFLOW_RUN.value
                task_type = StateEntityType.TASK_RUN.value
                att_type = StateEntityType.TASK_ATTEMPT.value

                trans_conds = [
                    (models.StateTransitionRow.entity_type == wf_type)
                    & models.StateTransitionRow.entity_id.in_(batch_run_ids)
                ]
                if task_run_ids:
                    trans_conds.append(
                        (models.StateTransitionRow.entity_type == task_type)
                        & models.StateTransitionRow.entity_id.in_(task_run_ids)
                    )
                if attempt_ids:
                    trans_conds.append(
                        (models.StateTransitionRow.entity_type == att_type)
                        & models.StateTransitionRow.entity_id.in_(attempt_ids)
                    )
                res_trans = session.execute(
                    delete(models.StateTransitionRow).where(or_(*trans_conds))
                )
                del_trans = int(cast(CursorResult[Any], res_trans).rowcount or 0)

                del_ext = 0
                if attempt_ids:
                    res_ext = session.execute(
                        delete(models.ExternalRunRefRow).where(
                            models.ExternalRunRefRow.attempt_id.in_(attempt_ids)
                        )
                    )
                    del_ext = int(cast(CursorResult[Any], res_ext).rowcount or 0)

                    del_att = 0
                    if task_run_ids:
                        res_att = session.execute(
                            delete(models.TaskAttemptRow).where(
                                models.TaskAttemptRow.task_run_id.in_(task_run_ids)
                            )
                        )
                        del_att = int(cast(CursorResult[Any], res_att).rowcount or 0)

                    res_tr = session.execute(
                        delete(models.TaskRunRow).where(
                            models.TaskRunRow.workflow_run_id.in_(batch_run_ids)
                        )
                    )
                    del_tr = int(cast(CursorResult[Any], res_tr).rowcount or 0)

                    res_m = session.execute(
                        delete(models.ManifestReferenceRow).where(
                            models.ManifestReferenceRow.workflow_run_id.in_(batch_run_ids)
                        )
                    )
                    del_m = int(cast(CursorResult[Any], res_m).rowcount or 0)

                    res_wf = session.execute(
                        delete(models.WorkflowRunRow).where(
                            models.WorkflowRunRow.run_id.in_(batch_run_ids)
                        )
                    )
                    del_wf = int(cast(CursorResult[Any], res_wf).rowcount or 0)

                    total_summary = DeletedRecordsSummary(
                        workflow_runs=total_summary.workflow_runs + del_wf,
                        task_runs=total_summary.task_runs + del_tr,
                        task_attempts=total_summary.task_attempts + del_att,
                        events=total_summary.events + del_trans,
                        checkpoints=total_summary.checkpoints + del_cp,
                        external_refs=total_summary.external_refs + del_ext,
                        manifests=total_summary.manifests + del_m,
                    )

        return PruneReport(
            dry_run=False,
            scanned_workflows=scanned_workflows,
            eligible_runs_to_prune=len(eligible_run_ids),
            deleted_records=total_summary,
        )

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
            raise MetadataInvariantError(reason="state transition evidence requires occurred_at")
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
            select(models.WorkflowRunRow.status).where(models.WorkflowRunRow.run_id == str(run_id))
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
                f"new {entity_type} {entity_id} must begin in {expected.value}; got {actual.value}"
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
        raise MetadataInvariantError(reason="WorkflowRun immutable identity fields changed")


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
        raise MetadataInvariantError(reason="TaskAttempt immutable identity fields changed")


def _require_transition_timestamp(
    current_status: str,
    candidate_status: str,
    transitioned_at: datetime | None,
) -> None:
    if current_status != candidate_status and transitioned_at is None:
        raise MetadataInvariantError(reason="status-changing update requires transitioned_at")


__all__ = [
    "DEFAULT_V2_SQLITE_PATH",
    "SQLiteMetadataStore",
    "SQLiteSettings",
]
