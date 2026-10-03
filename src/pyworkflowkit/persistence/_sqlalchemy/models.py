"""Internal SQLAlchemy rows for the canonical V2 MetadataStore."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from pyworkflowkit.persistence._sqlalchemy.base import (
    DB_SCHEMA,
    JSON_VALUE,
    Base,
    UTCDateTime,
)


class WorkflowRunRow(Base):
    __tablename__ = "v2_workflow_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED','CANCELLATION_REQUESTED',"
            "'CANCELLED','TIMED_OUT','UNKNOWN_OUTCOME')",
            name="status_valid",
        ),
        Index("ix_v2_workflow_runs_status", "status"),
        {"schema": DB_SCHEMA},
    )

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    workflow_name: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_version: Mapped[str] = mapped_column(Text, nullable=False)
    definition_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    plan_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    correlation_json: Mapped[dict[str, Any]] = mapped_column(JSON_VALUE, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failure_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)


class TaskRunRow(Base):
    __tablename__ = "v2_task_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','READY','RUNNING','SUCCEEDED','FAILED','SKIPPED',"
            "'CANCELLED','TIMED_OUT','BLOCKED','UNKNOWN_OUTCOME')",
            name="status_valid",
        ),
        Index("ix_v2_task_runs_workflow", "workflow_run_id", "task_key"),
        {"schema": DB_SCHEMA},
    )

    task_run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    workflow_run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(
            f"{DB_SCHEMA}.v2_workflow_runs.run_id",
            onupdate="RESTRICT",
            ondelete="CASCADE",
            name="fk_v2_task_runs_workflow_run",
        ),
        nullable=False,
    )
    task_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    skip_reason: Mapped[str | None] = mapped_column(Text)
    block_reason: Mapped[str | None] = mapped_column(Text)
    failure_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)


class TaskAttemptRow(Base):
    __tablename__ = "v2_task_attempts"
    __table_args__ = (
        UniqueConstraint(
            "task_run_id",
            "attempt_number",
            name="uq_v2_task_attempts_number",
        ),
        CheckConstraint("attempt_number >= 1", name="number_positive"),
        CheckConstraint(
            "status IN ('PENDING','STARTING','RUNNING','SUCCEEDED','FAILED','TIMED_OUT',"
            "'CANCELLATION_REQUESTED','CANCELLED','CANCELLATION_UNCONFIRMED',"
            "'UNKNOWN_OUTCOME','REQUIRES_RECONCILIATION')",
            name="status_valid",
        ),
        Index("ix_v2_task_attempts_task_run", "task_run_id", "attempt_number"),
        {"schema": DB_SCHEMA},
    )

    attempt_id: Mapped[str] = mapped_column(Text, primary_key=True)
    task_run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(
            f"{DB_SCHEMA}.v2_task_runs.task_run_id",
            onupdate="RESTRICT",
            ondelete="CASCADE",
            name="fk_v2_task_attempts_task_run",
        ),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    failure_json: Mapped[dict[str, Any] | None] = mapped_column(JSON_VALUE)


class ExternalRunRefRow(Base):
    __tablename__ = "v2_external_run_refs"
    __table_args__ = (
        UniqueConstraint(
            "attempt_id",
            "provider",
            "kind",
            "external_run_id",
            name="uq_v2_external_run_refs_identity",
        ),
        Index("ix_v2_external_run_refs_attempt", "attempt_id"),
        {"schema": DB_SCHEMA},
    )

    external_ref_pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attempt_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(
            f"{DB_SCHEMA}.v2_task_attempts.attempt_id",
            onupdate="RESTRICT",
            ondelete="CASCADE",
            name="fk_v2_external_run_refs_attempt",
        ),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    external_run_id: Mapped[str] = mapped_column(Text, nullable=False)
    status_hint: Mapped[str | None] = mapped_column(Text)
    status_locator: Mapped[str | None] = mapped_column(Text)
    correlation_id: Mapped[str | None] = mapped_column(Text)
    causation_id: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[list[list[str]]] = mapped_column(JSON_VALUE, nullable=False, default=list)
    namespace: Mapped[str] = mapped_column(Text, nullable=False)
    contract_version: Mapped[str] = mapped_column(Text, nullable=False)


class StateTransitionRow(Base):
    __tablename__ = "v2_state_transitions"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('workflow_run','task_run','task_attempt')",
            name="entity_type_valid",
        ),
        Index("ix_v2_state_transitions_entity", "entity_type", "entity_id", "sequence"),
        {"schema": DB_SCHEMA},
    )

    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class TaskOutputCheckpointRow(Base):
    __tablename__ = "v2_task_output_checkpoints"
    __table_args__ = ({"schema": DB_SCHEMA},)

    task_run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(
            f"{DB_SCHEMA}.v2_task_runs.task_run_id",
            onupdate="RESTRICT",
            ondelete="CASCADE",
            name="fk_v2_task_output_checkpoints_task_run",
        ),
        primary_key=True,
    )
    output_json: Mapped[Any] = mapped_column(JSON_VALUE, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    digest: Mapped[str] = mapped_column(Text, nullable=False)


class ManifestReferenceRow(Base):
    __tablename__ = "v2_manifest_references"
    __table_args__ = ({"schema": DB_SCHEMA},)

    workflow_run_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(
            f"{DB_SCHEMA}.v2_workflow_runs.run_id",
            onupdate="RESTRICT",
            ondelete="CASCADE",
            name="fk_v2_manifest_references_workflow_run",
        ),
        primary_key=True,
    )
    locator: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    digest: Mapped[str | None] = mapped_column(Text)


__all__ = [
    "ExternalRunRefRow",
    "ManifestReferenceRow",
    "StateTransitionRow",
    "TaskAttemptRow",
    "TaskOutputCheckpointRow",
    "TaskRunRow",
    "WorkflowRunRow",
]
