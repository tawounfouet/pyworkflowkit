"""Mappings between neutral persistence records and SQLAlchemy rows."""

from pyworkflowkit.adapters.metadata.sqlalchemy import models as orm_models
from pyworkflowkit.adapters.persistence.records import (
    ArtifactReferenceRow,
    ExternalRunRefRow,
    RuntimeEventRow,
    TaskAttemptRow,
    TaskRunRow,
    WorkflowRunRow,
)


class SqlAlchemyRowMapper:
    """Convert neutral row DTOs to/from SQLAlchemy mapped rows."""

    @staticmethod
    def workflow_run_to_orm(value: WorkflowRunRow) -> orm_models.WorkflowRunRow:
        return orm_models.WorkflowRunRow(
            run_id=value.run_id,
            workflow_id=value.workflow_id,
            workflow_version=value.workflow_version,
            status=value.status,
            parameters_json=dict(value.parameters),
            created_at=value.created_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
        )

    @staticmethod
    def workflow_run_from_orm(value: orm_models.WorkflowRunRow) -> WorkflowRunRow:
        return WorkflowRunRow(
            run_id=value.run_id,
            workflow_id=value.workflow_id,
            workflow_version=value.workflow_version,
            status=value.status,
            parameters=dict(value.parameters_json or {}),
            created_at=value.created_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
        )

    @staticmethod
    def apply_workflow_run(target: orm_models.WorkflowRunRow, value: WorkflowRunRow) -> None:
        target.workflow_id = value.workflow_id
        target.workflow_version = value.workflow_version
        target.status = value.status
        target.parameters_json = dict(value.parameters)
        target.created_at = value.created_at
        target.started_at = value.started_at
        target.finished_at = value.finished_at

    @staticmethod
    def task_run_to_orm(value: TaskRunRow) -> orm_models.TaskRunRow:
        return orm_models.TaskRunRow(
            task_run_id=value.task_run_id,
            run_id=value.run_id,
            task_id=value.task_id,
            status=value.status,
            skip_reason=value.skip_reason,
            created_at=value.created_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
        )

    @staticmethod
    def task_run_from_orm(value: orm_models.TaskRunRow) -> TaskRunRow:
        return TaskRunRow(
            task_run_id=value.task_run_id,
            run_id=value.run_id,
            task_id=value.task_id,
            status=value.status,
            skip_reason=value.skip_reason,
            created_at=value.created_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
        )

    @staticmethod
    def apply_task_run(target: orm_models.TaskRunRow, value: TaskRunRow) -> None:
        target.run_id = value.run_id
        target.task_id = value.task_id
        target.status = value.status
        target.skip_reason = value.skip_reason
        target.created_at = value.created_at
        target.started_at = value.started_at
        target.finished_at = value.finished_at

    @staticmethod
    def task_attempt_to_orm(value: TaskAttemptRow) -> orm_models.TaskAttemptRow:
        return orm_models.TaskAttemptRow(
            attempt_id=value.attempt_id,
            task_run_id=value.task_run_id,
            attempt_number=value.attempt_number,
            status=value.status,
            started_at=value.started_at,
            finished_at=value.finished_at,
            error_type=value.error_type,
            error_message=value.error_message,
            error_category=value.error_category,
            error_metadata_json=dict(value.error_metadata),
        )

    @staticmethod
    def task_attempt_from_orm(value: orm_models.TaskAttemptRow) -> TaskAttemptRow:
        return TaskAttemptRow(
            attempt_id=value.attempt_id,
            task_run_id=value.task_run_id,
            attempt_number=value.attempt_number,
            status=value.status,
            started_at=value.started_at,
            finished_at=value.finished_at,
            error_type=value.error_type,
            error_message=value.error_message,
            error_category=value.error_category,
            error_metadata=dict(value.error_metadata_json or {}),
        )

    @staticmethod
    def apply_task_attempt(
        target: orm_models.TaskAttemptRow,
        value: TaskAttemptRow,
    ) -> None:
        target.task_run_id = value.task_run_id
        target.attempt_number = value.attempt_number
        target.status = value.status
        target.started_at = value.started_at
        target.finished_at = value.finished_at
        target.error_type = value.error_type
        target.error_message = value.error_message
        target.error_category = value.error_category
        target.error_metadata_json = dict(value.error_metadata)

    @staticmethod
    def runtime_event_to_orm(value: RuntimeEventRow) -> orm_models.RuntimeEventRow:
        return orm_models.RuntimeEventRow(
            event_id=value.event_id,
            event_type=value.event_type,
            run_id=value.run_id,
            occurred_at=value.occurred_at,
            event_sequence=value.event_sequence,
            task_run_id=value.task_run_id,
            task_id=value.task_id,
            attempt_number=value.attempt_number,
            payload_json=dict(value.payload),
        )

    @staticmethod
    def runtime_event_from_orm(value: orm_models.RuntimeEventRow) -> RuntimeEventRow:
        return RuntimeEventRow(
            event_id=value.event_id,
            event_type=value.event_type,
            run_id=value.run_id,
            occurred_at=value.occurred_at,
            event_sequence=value.event_sequence,
            task_run_id=value.task_run_id,
            task_id=value.task_id,
            attempt_number=value.attempt_number,
            payload=dict(value.payload_json or {}),
        )

    @staticmethod
    def artifact_to_orm(value: ArtifactReferenceRow) -> orm_models.ArtifactReferenceRow:
        return orm_models.ArtifactReferenceRow(
            artifact_id=value.artifact_id,
            task_run_id=value.task_run_id,
            name=value.name,
            uri=value.uri,
            media_type=value.media_type,
            checksum=value.checksum,
            size_bytes=value.size_bytes,
            metadata_json=dict(value.metadata),
        )

    @staticmethod
    def artifact_from_orm(value: orm_models.ArtifactReferenceRow) -> ArtifactReferenceRow:
        return ArtifactReferenceRow(
            artifact_id=value.artifact_id,
            task_run_id=value.task_run_id,
            name=value.name,
            uri=value.uri,
            media_type=value.media_type,
            checksum=value.checksum,
            size_bytes=value.size_bytes,
            metadata=dict(value.metadata_json or {}),
        )

    @staticmethod
    def external_ref_to_orm(value: ExternalRunRefRow) -> orm_models.ExternalRunRefRow:
        return orm_models.ExternalRunRefRow(
            external_ref_id=value.external_ref_id,
            task_run_id=value.task_run_id,
            provider=value.provider,
            external_run_id=value.external_run_id,
            uri=value.uri,
            metadata_json=dict(value.metadata),
        )

    @staticmethod
    def external_ref_from_orm(value: orm_models.ExternalRunRefRow) -> ExternalRunRefRow:
        return ExternalRunRefRow(
            external_ref_id=value.external_ref_id,
            task_run_id=value.task_run_id,
            provider=value.provider,
            external_run_id=value.external_run_id,
            uri=value.uri,
            metadata=dict(value.metadata_json or {}),
        )


__all__ = ["SqlAlchemyRowMapper"]
