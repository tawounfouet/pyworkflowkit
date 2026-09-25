"""Explicit domain-to-row mappings for persistence adapters."""

from pyworkflowkit.adapters.persistence.records import (
    ArtifactReferenceRow,
    ExternalRunRefRow,
    RuntimeEventRow,
    TaskAttemptRow,
    TaskRunRow,
    WorkflowRunRow,
)
from pyworkflowkit.application.mapping import DomainSchemaMapper
from pyworkflowkit.contracts.serialization import (
    ArtifactReferenceSchema,
    ExternalRunRefSchema,
    RuntimeEventSchema,
    TaskAttemptSchema,
    TaskRunSchema,
    WorkflowRunSchema,
)
from pyworkflowkit.domain.enums import (
    RuntimeEventType,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import TaskRunId
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef


class PersistenceMapper:
    """Map domain runtime values to neutral persistence rows and back."""

    @staticmethod
    def workflow_run_to_row(value: WorkflowRun) -> WorkflowRunRow:
        schema = DomainSchemaMapper.workflow_run_to_schema(value)
        return WorkflowRunRow(
            run_id=schema.run_id,
            workflow_id=schema.workflow_id,
            workflow_version=schema.workflow_version,
            status=schema.status.value,
            parameters=dict(schema.parameters),
            created_at=schema.created_at,
            started_at=schema.started_at,
            finished_at=schema.finished_at,
        )

    @staticmethod
    def workflow_run_from_row(value: WorkflowRunRow) -> WorkflowRun:
        schema = WorkflowRunSchema(
            run_id=value.run_id,
            workflow_id=value.workflow_id,
            workflow_version=value.workflow_version,
            status=WorkflowRunStatus(value.status),
            parameters=dict(value.parameters),
            created_at=value.created_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
        )
        return DomainSchemaMapper.workflow_run_from_schema(schema)

    @staticmethod
    def task_run_to_row(value: TaskRun) -> TaskRunRow:
        schema = DomainSchemaMapper.task_run_to_schema(value)
        return TaskRunRow(
            task_run_id=schema.task_run_id,
            run_id=schema.run_id,
            task_id=schema.task_id,
            status=schema.status.value,
            skip_reason=(
                schema.skip_reason.value if schema.skip_reason is not None else None
            ),
            created_at=schema.created_at,
            started_at=schema.started_at,
            finished_at=schema.finished_at,
        )

    @staticmethod
    def task_run_from_row(value: TaskRunRow) -> TaskRun:
        schema = TaskRunSchema(
            task_run_id=value.task_run_id,
            run_id=value.run_id,
            task_id=value.task_id,
            status=TaskRunStatus(value.status),
            skip_reason=(
                SkipReason(value.skip_reason) if value.skip_reason is not None else None
            ),
            created_at=value.created_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
        )
        return DomainSchemaMapper.task_run_from_schema(schema)

    @staticmethod
    def task_attempt_to_row(value: TaskAttempt) -> TaskAttemptRow:
        schema = DomainSchemaMapper.task_attempt_to_schema(value)
        return TaskAttemptRow(
            attempt_id=schema.attempt_id,
            task_run_id=schema.task_run_id,
            attempt_number=schema.attempt_number,
            status=schema.status.value,
            started_at=schema.started_at,
            finished_at=schema.finished_at,
            error_type=schema.error_type,
            error_message=schema.error_message,
            error_category=schema.error_category,
            error_metadata=dict(schema.error_metadata),
        )

    @staticmethod
    def task_attempt_from_row(value: TaskAttemptRow) -> TaskAttempt:
        schema = TaskAttemptSchema(
            attempt_id=value.attempt_id,
            task_run_id=value.task_run_id,
            attempt_number=value.attempt_number,
            status=TaskAttemptStatus(value.status),
            started_at=value.started_at,
            finished_at=value.finished_at,
            error_type=value.error_type,
            error_message=value.error_message,
            error_category=value.error_category,
            error_metadata=dict(value.error_metadata),
        )
        return DomainSchemaMapper.task_attempt_from_schema(schema)

    @staticmethod
    def runtime_event_to_row(value: RuntimeEvent) -> RuntimeEventRow:
        schema = DomainSchemaMapper.runtime_event_to_schema(value)
        return RuntimeEventRow(
            event_id=schema.event_id,
            event_type=schema.event_type.value,
            run_id=schema.run_id,
            occurred_at=schema.occurred_at,
            event_sequence=schema.event_sequence,
            task_run_id=schema.task_run_id,
            task_id=schema.task_id,
            attempt_number=schema.attempt_number,
            payload=dict(schema.payload),
        )

    @staticmethod
    def runtime_event_from_row(value: RuntimeEventRow) -> RuntimeEvent:
        schema = RuntimeEventSchema(
            event_id=value.event_id,
            event_type=RuntimeEventType(value.event_type),
            run_id=value.run_id,
            occurred_at=value.occurred_at,
            event_sequence=value.event_sequence,
            task_run_id=value.task_run_id,
            task_id=value.task_id,
            attempt_number=value.attempt_number,
            payload=dict(value.payload),
        )
        return DomainSchemaMapper.runtime_event_from_schema(schema)

    @staticmethod
    def artifact_to_row(
        *,
        task_run_id: TaskRunId,
        value: ArtifactReference,
    ) -> ArtifactReferenceRow:
        schema = DomainSchemaMapper.artifact_to_schema(value)
        return ArtifactReferenceRow(
            artifact_id=schema.artifact_id,
            task_run_id=str(task_run_id),
            name=schema.name,
            uri=schema.uri,
            media_type=schema.media_type,
            checksum=schema.checksum,
            size_bytes=schema.size_bytes,
            metadata=dict(schema.metadata),
        )

    @staticmethod
    def artifact_from_row(
        value: ArtifactReferenceRow,
    ) -> tuple[TaskRunId, ArtifactReference]:
        schema = ArtifactReferenceSchema(
            artifact_id=value.artifact_id,
            name=value.name,
            uri=value.uri,
            media_type=value.media_type,
            checksum=value.checksum,
            size_bytes=value.size_bytes,
            metadata=dict(value.metadata),
        )
        return TaskRunId(value.task_run_id), DomainSchemaMapper.artifact_from_schema(
            schema
        )

    @staticmethod
    def external_ref_to_row(
        *,
        task_run_id: TaskRunId,
        value: ExternalRunRef,
    ) -> ExternalRunRefRow:
        schema = DomainSchemaMapper.external_ref_to_schema(value)
        return ExternalRunRefRow(
            external_ref_id=schema.external_ref_id,
            task_run_id=str(task_run_id),
            provider=schema.provider,
            external_run_id=schema.external_run_id,
            uri=schema.uri,
            metadata=dict(schema.metadata),
        )

    @staticmethod
    def external_ref_from_row(
        value: ExternalRunRefRow,
    ) -> tuple[TaskRunId, ExternalRunRef]:
        schema = ExternalRunRefSchema(
            external_ref_id=value.external_ref_id,
            provider=value.provider,
            external_run_id=value.external_run_id,
            uri=value.uri,
            metadata=dict(value.metadata),
        )
        return TaskRunId(value.task_run_id), DomainSchemaMapper.external_ref_from_schema(
            schema
        )


__all__ = ["PersistenceMapper"]
