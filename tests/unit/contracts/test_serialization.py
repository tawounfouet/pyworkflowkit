"""Tests for strict boundary schemas and explicit domain mappings."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from pyworkflowkit.application.mapping import DomainSchemaMapper
from pyworkflowkit.contracts.serialization import (
    RuntimeEventSchema,
    SchemaCodec,
    WorkflowRunSchema,
)
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    BackoffStrategy,
    RuntimeEventType,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import (
    RuntimeEventId,
    TaskId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import RuntimeEvent, WorkflowRun
from pyworkflowkit.domain.values import RetryPolicy, WorkflowParameter
from pyworkflowkit.errors import SerializationError


def test_workflow_definition_domain_schema_round_trip() -> None:
    definition = WorkflowDefinition(
        workflow_id=WorkflowId("pipeline"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("fetch"),
                handler_ref="handlers:fetch",
                retry_policy=RetryPolicy(
                    max_attempts=3,
                    backoff_strategy=BackoffStrategy.EXPONENTIAL,
                    delay_seconds=2.0,
                    max_delay_seconds=10.0,
                    retryable_error_categories=frozenset(
                        {"TimeoutError", "ConnectionError"}
                    ),
                ),
                tags=frozenset({"io", "source"}),
            ),
            TaskDefinition(
                task_id=TaskId("publish"),
                handler_ref="handlers:publish",
                depends_on=(TaskId("fetch"),),
            ),
        ),
        parameters=(
            WorkflowParameter(name="source"),
            WorkflowParameter(
                name="options",
                required=False,
                default={"batch": [1, 2, 3]},
            ),
        ),
    )

    schema = DomainSchemaMapper.workflow_definition_to_schema(definition)
    restored = DomainSchemaMapper.workflow_definition_from_schema(schema)

    assert restored == definition
    assert schema.tasks[0].tags == ("io", "source")
    assert schema.tasks[0].retry_policy.retryable_error_categories == (
        "ConnectionError",
        "TimeoutError",
    )


def test_schema_codec_is_canonical_and_round_trips() -> None:
    schema = WorkflowRunSchema(
        run_id="run-1",
        workflow_id="workflow",
        workflow_version="1",
        status=WorkflowRunStatus.PENDING,
        parameters={"z": 1, "a": {"b": [2, 3]}},
    )

    encoded = SchemaCodec.to_json(schema)
    decoded = SchemaCodec.from_json(WorkflowRunSchema, encoded)

    assert decoded == schema
    assert encoded == (
        '{"created_at":null,"finished_at":null,"parameters":{"a":{"b":[2,3]},"z":1},'
        '"run_id":"run-1","started_at":null,"status":"PENDING",'
        '"workflow_id":"workflow","workflow_version":"1"}'
    )


def test_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        WorkflowRunSchema.model_validate(
            {
                "run_id": "run-1",
                "workflow_id": "workflow",
                "workflow_version": "1",
                "status": "PENDING",
                "parameters": {},
                "unexpected": True,
            }
        )


def test_runtime_datetime_is_normalized_to_utc() -> None:
    plus_two = timezone_plus_two()
    created_at = datetime(2026, 9, 25, 22, 0, tzinfo=plus_two)
    run = WorkflowRun(
        run_id=WorkflowRunId("run-1"),
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
        created_at=created_at,
    )

    schema = DomainSchemaMapper.workflow_run_to_schema(run)
    restored = DomainSchemaMapper.workflow_run_from_schema(schema)

    assert schema.created_at == datetime(2026, 9, 25, 20, 0, tzinfo=UTC)
    assert restored.created_at == datetime(2026, 9, 25, 20, 0, tzinfo=UTC)


def test_schema_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        WorkflowRunSchema(
            run_id="run-1",
            workflow_id="workflow",
            workflow_version="1",
            status=WorkflowRunStatus.PENDING,
            parameters={},
            created_at=datetime(2026, 9, 25, 20, 0),
        )


def test_mapping_rejects_non_json_portable_runtime_value() -> None:
    class Unsupported:
        pass

    run = WorkflowRun(
        run_id=WorkflowRunId("run-1"),
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
        parameters={"bad": Unsupported()},
    )

    with pytest.raises(SerializationError) as exc_info:
        DomainSchemaMapper.workflow_run_to_schema(run)

    assert exc_info.value.path == "workflow_run.parameters.bad"
    assert exc_info.value.value_type == "Unsupported"


def test_workflow_parameter_mapping_rejects_non_json_portable_default() -> None:
    parameter = WorkflowParameter(name="bad", default=object())

    with pytest.raises(SerializationError, match="portable JSON"):
        DomainSchemaMapper.workflow_parameter_to_schema(parameter)


def test_runtime_event_schema_round_trip_preserves_sequence_and_context() -> None:
    occurred_at = datetime(2026, 9, 25, 20, 0, tzinfo=UTC)
    event = RuntimeEvent(
        event_id=RuntimeEventId("event-4"),
        event_type=RuntimeEventType.TASK_SUCCEEDED,
        run_id=WorkflowRunId("run-1"),
        occurred_at=occurred_at,
        event_sequence=4,
        task_id=TaskId("A"),
        attempt_number=2,
        payload={"rows": 10},
    )

    schema = DomainSchemaMapper.runtime_event_to_schema(event)
    encoded = SchemaCodec.to_json(schema)
    decoded = SchemaCodec.from_json(RuntimeEventSchema, encoded)
    restored = DomainSchemaMapper.runtime_event_from_schema(decoded)

    assert restored == event
    assert decoded.event_sequence == 4
    assert decoded.occurred_at.tzinfo is UTC


def timezone_plus_two() -> timezone:
    return timezone(timedelta(hours=2))
