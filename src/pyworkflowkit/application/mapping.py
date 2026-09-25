"""Explicit mappings between domain objects and boundary schemas."""

from pyworkflowkit.contracts.serialization import (
    ArtifactReferenceSchema,
    ExternalRunRefSchema,
    RetryPolicySchema,
    RuntimeEventSchema,
    TaskAttemptSchema,
    TaskDefinitionSchema,
    TaskRunSchema,
    WorkflowDefinitionSchema,
    WorkflowParameterSchema,
    WorkflowRunSchema,
)
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.ids import (
    ArtifactId,
    ExternalRunRefId,
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import (
    ArtifactReference,
    ExternalRunRef,
    RetryPolicy,
    WorkflowParameter,
)


class DomainSchemaMapper:
    """Map domain values explicitly to/from strict serialization schemas."""

    @staticmethod
    def retry_policy_to_schema(value: RetryPolicy) -> RetryPolicySchema:
        return RetryPolicySchema(
            max_attempts=value.max_attempts,
            backoff_strategy=value.backoff_strategy,
            delay_seconds=value.delay_seconds,
            max_delay_seconds=value.max_delay_seconds,
            retryable_error_categories=tuple(sorted(value.retryable_error_categories)),
        )

    @staticmethod
    def retry_policy_from_schema(value: RetryPolicySchema) -> RetryPolicy:
        return RetryPolicy(
            max_attempts=value.max_attempts,
            backoff_strategy=value.backoff_strategy,
            delay_seconds=value.delay_seconds,
            max_delay_seconds=value.max_delay_seconds,
            retryable_error_categories=frozenset(value.retryable_error_categories),
        )

    @staticmethod
    def workflow_parameter_to_schema(value: WorkflowParameter) -> WorkflowParameterSchema:
        return WorkflowParameterSchema(
            name=value.name,
            required=value.required,
            default=value.default,
            sensitive=value.sensitive,
        )

    @staticmethod
    def workflow_parameter_from_schema(value: WorkflowParameterSchema) -> WorkflowParameter:
        return WorkflowParameter(
            name=value.name,
            required=value.required,
            default=value.default,
            sensitive=value.sensitive,
        )

    @classmethod
    def task_definition_to_schema(cls, value: TaskDefinition) -> TaskDefinitionSchema:
        return TaskDefinitionSchema(
            task_id=str(value.task_id),
            handler_ref=value.handler_ref,
            depends_on=tuple(str(task_id) for task_id in value.depends_on),
            retry_policy=cls.retry_policy_to_schema(value.retry_policy),
            executor_key=value.executor_key,
            timeout_seconds=value.timeout_seconds,
            tags=tuple(sorted(value.tags)),
            description=value.description,
        )

    @classmethod
    def task_definition_from_schema(cls, value: TaskDefinitionSchema) -> TaskDefinition:
        return TaskDefinition(
            task_id=TaskId(value.task_id),
            handler_ref=value.handler_ref,
            depends_on=tuple(TaskId(task_id) for task_id in value.depends_on),
            retry_policy=cls.retry_policy_from_schema(value.retry_policy),
            executor_key=value.executor_key,
            timeout_seconds=value.timeout_seconds,
            tags=frozenset(value.tags),
            description=value.description,
        )

    @classmethod
    def workflow_definition_to_schema(
        cls,
        value: WorkflowDefinition,
    ) -> WorkflowDefinitionSchema:
        return WorkflowDefinitionSchema(
            workflow_id=str(value.workflow_id),
            version=value.version,
            tasks=tuple(cls.task_definition_to_schema(task) for task in value.tasks),
            parameters=tuple(
                cls.workflow_parameter_to_schema(parameter)
                for parameter in value.parameters
            ),
            failure_policy=value.failure_policy,
            description=value.description,
        )

    @classmethod
    def workflow_definition_from_schema(
        cls,
        value: WorkflowDefinitionSchema,
    ) -> WorkflowDefinition:
        return WorkflowDefinition(
            workflow_id=WorkflowId(value.workflow_id),
            version=value.version,
            tasks=tuple(cls.task_definition_from_schema(task) for task in value.tasks),
            parameters=tuple(
                cls.workflow_parameter_from_schema(parameter)
                for parameter in value.parameters
            ),
            failure_policy=value.failure_policy,
            description=value.description,
        )

    @staticmethod
    def workflow_run_to_schema(value: WorkflowRun) -> WorkflowRunSchema:
        return WorkflowRunSchema(
            run_id=str(value.run_id),
            workflow_id=str(value.workflow_id),
            workflow_version=value.workflow_version,
            status=value.status,
            parameters=dict(value.parameters),
            created_at=value.created_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
        )

    @staticmethod
    def workflow_run_from_schema(value: WorkflowRunSchema) -> WorkflowRun:
        return WorkflowRun(
            run_id=WorkflowRunId(value.run_id),
            workflow_id=WorkflowId(value.workflow_id),
            workflow_version=value.workflow_version,
            status=value.status,
            parameters=dict(value.parameters),
            created_at=value.created_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
        )

    @staticmethod
    def task_run_to_schema(value: TaskRun) -> TaskRunSchema:
        return TaskRunSchema(
            task_run_id=str(value.task_run_id),
            run_id=str(value.run_id),
            task_id=str(value.task_id),
            status=value.status,
            skip_reason=value.skip_reason,
            created_at=value.created_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
        )

    @staticmethod
    def task_run_from_schema(value: TaskRunSchema) -> TaskRun:
        return TaskRun(
            task_run_id=TaskRunId(value.task_run_id),
            run_id=WorkflowRunId(value.run_id),
            task_id=TaskId(value.task_id),
            status=value.status,
            skip_reason=value.skip_reason,
            created_at=value.created_at,
            started_at=value.started_at,
            finished_at=value.finished_at,
        )

    @staticmethod
    def task_attempt_to_schema(value: TaskAttempt) -> TaskAttemptSchema:
        return TaskAttemptSchema(
            attempt_id=str(value.attempt_id),
            task_run_id=str(value.task_run_id),
            attempt_number=value.attempt_number,
            status=value.status,
            started_at=value.started_at,
            finished_at=value.finished_at,
            error_type=value.error_type,
            error_message=value.error_message,
            error_category=value.error_category,
            error_metadata=dict(value.error_metadata),
        )

    @staticmethod
    def task_attempt_from_schema(value: TaskAttemptSchema) -> TaskAttempt:
        return TaskAttempt(
            attempt_id=TaskAttemptId(value.attempt_id),
            task_run_id=TaskRunId(value.task_run_id),
            attempt_number=value.attempt_number,
            status=value.status,
            started_at=value.started_at,
            finished_at=value.finished_at,
            error_type=value.error_type,
            error_message=value.error_message,
            error_category=value.error_category,
            error_metadata=dict(value.error_metadata),
        )

    @staticmethod
    def runtime_event_to_schema(value: RuntimeEvent) -> RuntimeEventSchema:
        return RuntimeEventSchema(
            event_id=str(value.event_id),
            event_type=value.event_type,
            run_id=str(value.run_id),
            occurred_at=value.occurred_at,
            event_sequence=value.event_sequence,
            task_run_id=(
                str(value.task_run_id) if value.task_run_id is not None else None
            ),
            task_id=str(value.task_id) if value.task_id is not None else None,
            attempt_number=value.attempt_number,
            payload=dict(value.payload),
        )

    @staticmethod
    def runtime_event_from_schema(value: RuntimeEventSchema) -> RuntimeEvent:
        return RuntimeEvent(
            event_id=RuntimeEventId(value.event_id),
            event_type=value.event_type,
            run_id=WorkflowRunId(value.run_id),
            occurred_at=value.occurred_at,
            event_sequence=value.event_sequence,
            task_run_id=(
                TaskRunId(value.task_run_id) if value.task_run_id is not None else None
            ),
            task_id=TaskId(value.task_id) if value.task_id is not None else None,
            attempt_number=value.attempt_number,
            payload=dict(value.payload),
        )

    @staticmethod
    def artifact_to_schema(value: ArtifactReference) -> ArtifactReferenceSchema:
        return ArtifactReferenceSchema(
            artifact_id=str(value.artifact_id),
            name=value.name,
            uri=value.uri,
            media_type=value.media_type,
            checksum=value.checksum,
            size_bytes=value.size_bytes,
            metadata=dict(value.metadata),
        )

    @staticmethod
    def artifact_from_schema(value: ArtifactReferenceSchema) -> ArtifactReference:
        return ArtifactReference(
            artifact_id=ArtifactId(value.artifact_id),
            name=value.name,
            uri=value.uri,
            media_type=value.media_type,
            checksum=value.checksum,
            size_bytes=value.size_bytes,
            metadata=dict(value.metadata),
        )

    @staticmethod
    def external_ref_to_schema(value: ExternalRunRef) -> ExternalRunRefSchema:
        return ExternalRunRefSchema(
            external_ref_id=str(value.external_ref_id),
            provider=value.provider,
            external_run_id=value.external_run_id,
            uri=value.uri,
            metadata=dict(value.metadata),
        )

    @staticmethod
    def external_ref_from_schema(value: ExternalRunRefSchema) -> ExternalRunRef:
        return ExternalRunRef(
            external_ref_id=ExternalRunRefId(value.external_ref_id),
            provider=value.provider,
            external_run_id=value.external_run_id,
            uri=value.uri,
            metadata=dict(value.metadata),
        )


__all__ = ["DomainSchemaMapper"]
