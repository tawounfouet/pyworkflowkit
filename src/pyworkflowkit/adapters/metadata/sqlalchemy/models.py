"""Dialect-neutral SQLAlchemy runtime/evidence rows for MetadataStore."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from pyworkflowkit.adapters.metadata.sqlalchemy.base import (
    DB_SCHEMA,
    JSON_VALUE,
    Base,
    RuntimeIdType,
    UTCDateTime,
)


class WorkflowRunRow(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="status_valid",
        ),
        Index("ix_workflow_runs_workflow", "workflow_id", "workflow_version"),
        {"schema": DB_SCHEMA},
    )

    run_id: Mapped[str] = mapped_column(RuntimeIdType(), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_VALUE, nullable=False, default=dict
    )
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class TaskRunRow(Base):
    __tablename__ = "task_runs"
    __table_args__ = (
        UniqueConstraint("run_id", "task_id", name="uq_task_runs_run_task"),
        CheckConstraint(
            "status IN ('PENDING','READY','RUNNING','SUCCEEDED','FAILED','SKIPPED','CANCELLED')",
            name="status_valid",
        ),
        Index("ix_task_runs_run", "run_id"),
        {"schema": DB_SCHEMA},
    )

    task_run_id: Mapped[str] = mapped_column(RuntimeIdType(), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        RuntimeIdType(),
        ForeignKey(
            f"{DB_SCHEMA}.workflow_runs.run_id",
            onupdate="RESTRICT",
            ondelete="CASCADE",
            name="fk_task_runs_workflow_run",
        ),
        nullable=False,
    )
    task_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class TaskAttemptRow(Base):
    __tablename__ = "task_attempts"
    __table_args__ = (
        UniqueConstraint("task_run_id", "attempt_number", name="uq_task_attempts_number"),
        CheckConstraint("attempt_number >= 1", name="number_positive"),
        CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED','CANCELLED')",
            name="status_valid",
        ),
        Index("ix_task_attempts_task_run", "task_run_id", "attempt_number"),
        Index(
            "uq_task_attempts_one_running",
            "task_run_id",
            unique=True,
            postgresql_where=text("status = 'RUNNING'"),
        ).ddl_if(dialect="postgresql"),
        {"schema": DB_SCHEMA},
    )

    attempt_id: Mapped[str] = mapped_column(RuntimeIdType(), primary_key=True)
    task_run_id: Mapped[str] = mapped_column(
        RuntimeIdType(),
        ForeignKey(
            f"{DB_SCHEMA}.task_runs.task_run_id",
            onupdate="RESTRICT",
            ondelete="CASCADE",
            name="fk_task_attempts_task_run",
        ),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_type: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_category: Mapped[str | None] = mapped_column(Text)
    error_metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON_VALUE, nullable=False, default=dict
    )


class RuntimeEventRow(Base):
    __tablename__ = "runtime_events"
    __table_args__ = (
        UniqueConstraint("run_id", "event_sequence", name="uq_runtime_events_sequence"),
        CheckConstraint(
            """
            event_type IN (
              'WORKFLOW_STARTED','WORKFLOW_SUCCEEDED','WORKFLOW_FAILED',
              'WORKFLOW_CANCELLED','TASK_READY','TASK_STARTED','TASK_RETRYING',
              'TASK_SUCCEEDED','TASK_FAILED','TASK_SKIPPED'
            )
            """,
            name="event_type_valid",
        ),
        Index("ix_runtime_events_run", "run_id", "event_sequence"),
        {"schema": DB_SCHEMA},
    )

    event_id: Mapped[str] = mapped_column(RuntimeIdType(), primary_key=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(
        RuntimeIdType(),
        ForeignKey(
            f"{DB_SCHEMA}.workflow_runs.run_id",
            onupdate="RESTRICT",
            ondelete="CASCADE",
            name="fk_runtime_events_run",
        ),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    event_sequence: Mapped[int | None] = mapped_column(Integer)
    task_run_id: Mapped[str | None] = mapped_column(
        RuntimeIdType(),
        ForeignKey(
            f"{DB_SCHEMA}.task_runs.task_run_id",
            onupdate="RESTRICT",
            ondelete="CASCADE",
            name="fk_runtime_events_task_run",
        ),
    )
    task_id: Mapped[str | None] = mapped_column(Text)
    attempt_number: Mapped[int | None] = mapped_column(Integer)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)


class ArtifactReferenceRow(Base):
    __tablename__ = "artifact_references"
    __table_args__ = (
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="size_nonnegative"),
        Index("ix_artifact_references_task", "task_run_id"),
        {"schema": DB_SCHEMA},
    )

    artifact_id: Mapped[str] = mapped_column(Text, primary_key=True)
    task_run_id: Mapped[str] = mapped_column(
        RuntimeIdType(),
        ForeignKey(
            f"{DB_SCHEMA}.task_runs.task_run_id",
            onupdate="RESTRICT",
            ondelete="CASCADE",
            name="fk_artifact_references_task_run",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)


class ExternalRunRefRow(Base):
    __tablename__ = "external_run_refs"
    __table_args__ = (
        UniqueConstraint(
            "task_run_id",
            "provider",
            "external_run_id",
            name="uq_external_run_refs_identity",
        ),
        Index("ix_external_run_refs_task", "task_run_id"),
        {"schema": DB_SCHEMA},
    )

    external_ref_id: Mapped[str] = mapped_column(Text, primary_key=True)
    task_run_id: Mapped[str] = mapped_column(
        RuntimeIdType(),
        ForeignKey(
            f"{DB_SCHEMA}.task_runs.task_run_id",
            onupdate="RESTRICT",
            ondelete="CASCADE",
            name="fk_external_run_refs_task_run",
        ),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    external_run_id: Mapped[str] = mapped_column(Text, nullable=False)
    uri: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False, default=dict)


__all__ = [
    "ArtifactReferenceRow",
    "ExternalRunRefRow",
    "RuntimeEventRow",
    "TaskAttemptRow",
    "TaskRunRow",
    "WorkflowRunRow",
]
