"""Domain ↔ SQLAlchemy mapping for canonical V2 runtime persistence."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pyworkflowkit.diagnostics import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.persistence._sqlalchemy import models
from pyworkflowkit.persistence.contracts import (
    ManifestReference,
    StateEntityType,
    StateTransitionRecord,
)
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    ExternalRunRef,
    TaskAttempt,
    TaskAttemptId,
    TaskRun,
    TaskRunId,
    WorkflowRun,
    WorkflowRunId,
)
from pyworkflowkit.states import (
    BlockReason,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)


def _pairs_to_json(values: tuple[tuple[str, str], ...]) -> list[list[str]]:
    return [[key, value] for key, value in values]


def _pairs_from_json(values: object) -> tuple[tuple[str, str], ...]:
    if values is None:
        return ()
    if not isinstance(values, list):
        raise TypeError("persisted pair collection must be a list")
    pairs: list[tuple[str, str]] = []
    for item in values:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not all(isinstance(value, str) for value in item)
        ):
            raise TypeError("persisted pair collection contains an invalid entry")
        pairs.append((item[0], item[1]))
    return tuple(pairs)


def correlation_to_json(value: CorrelationContext) -> dict[str, str | None]:
    return {
        "correlation_id": str(value.correlation_id),
        "causation_id": value.causation_id,
        "parent_execution_id": value.parent_execution_id,
        "workflow_run_id": value.workflow_run_id,
        "task_run_id": value.task_run_id,
        "task_attempt_id": value.task_attempt_id,
        "ingestion_run_id": value.ingestion_run_id,
        "transformation_execution_id": value.transformation_execution_id,
        "trace_id": value.trace_id,
        "span_id": value.span_id,
    }


def correlation_from_json(value: Mapping[str, Any]) -> CorrelationContext:
    return CorrelationContext(
        correlation_id=CorrelationId.parse(str(value["correlation_id"])),
        causation_id=_optional_string(value.get("causation_id")),
        parent_execution_id=_optional_string(value.get("parent_execution_id")),
        workflow_run_id=_optional_string(value.get("workflow_run_id")),
        task_run_id=_optional_string(value.get("task_run_id")),
        task_attempt_id=_optional_string(value.get("task_attempt_id")),
        ingestion_run_id=_optional_string(value.get("ingestion_run_id")),
        transformation_execution_id=_optional_string(
            value.get("transformation_execution_id")
        ),
        trace_id=_optional_string(value.get("trace_id")),
        span_id=_optional_string(value.get("span_id")),
    )


def external_ref_to_json(value: ExternalRunRef) -> dict[str, Any]:
    return {
        "provider": value.provider,
        "external_run_id": value.external_run_id,
        "kind": value.kind,
        "status_hint": value.status_hint,
        "status_locator": value.status_locator,
        "correlation_id": (
            str(value.correlation_id) if value.correlation_id is not None else None
        ),
        "causation_id": value.causation_id,
        "metadata": _pairs_to_json(value.metadata),
        "namespace": value.namespace,
        "contract_version": value.contract_version,
    }


def external_ref_from_json(value: Mapping[str, Any]) -> ExternalRunRef:
    correlation_id = _optional_string(value.get("correlation_id"))
    return ExternalRunRef(
        provider=str(value["provider"]),
        external_run_id=str(value["external_run_id"]),
        kind=str(value["kind"]),
        status_hint=_optional_string(value.get("status_hint")),
        status_locator=_optional_string(value.get("status_locator")),
        correlation_id=(
            CorrelationId.parse(correlation_id) if correlation_id is not None else None
        ),
        causation_id=_optional_string(value.get("causation_id")),
        metadata=_pairs_from_json(value.get("metadata")),
        namespace=str(value.get("namespace", "pyworkflowkit.external_run")),
        contract_version=str(value.get("contract_version", "1")),
    )


def failure_to_json(value: FailureEvidence | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "error_code": value.error_code,
        "category": value.category.value,
        "retryability": value.retryability.value,
        "uncertainty": value.uncertainty.value,
        "correlation_id": str(value.correlation_id),
        "source_framework": value.source_framework,
        "workflow_run_id": value.workflow_run_id,
        "task_run_id": value.task_run_id,
        "task_attempt_id": value.task_attempt_id,
        "external_run": (
            external_ref_to_json(value.external_run)
            if value.external_run is not None
            else None
        ),
        "source_component": value.source_component,
        "provider_code": value.provider_code,
        "message_summary": value.message_summary,
        "occurred_at": value.occurred_at.isoformat(),
        "details": _pairs_to_json(value.details),
        "contract_version": value.contract_version,
    }


def failure_from_json(value: Mapping[str, Any] | None) -> FailureEvidence | None:
    if value is None:
        return None
    external = value.get("external_run")
    if external is not None and not isinstance(external, Mapping):
        raise TypeError("persisted external_run failure evidence must be an object")
    return FailureEvidence(
        error_code=str(value["error_code"]),
        category=FailureCategory(str(value["category"])),
        retryability=Retryability(str(value["retryability"])),
        uncertainty=OutcomeUncertainty(str(value["uncertainty"])),
        correlation_id=CorrelationId.parse(str(value["correlation_id"])),
        source_framework=str(value.get("source_framework", "pyworkflowkit")),
        workflow_run_id=_optional_string(value.get("workflow_run_id")),
        task_run_id=_optional_string(value.get("task_run_id")),
        task_attempt_id=_optional_string(value.get("task_attempt_id")),
        external_run=external_ref_from_json(external) if external is not None else None,
        source_component=_optional_string(value.get("source_component")),
        provider_code=_optional_string(value.get("provider_code")),
        message_summary=_optional_string(value.get("message_summary")),
        occurred_at=datetime.fromisoformat(str(value["occurred_at"])),
        details=_pairs_from_json(value.get("details")),
        contract_version=str(value.get("contract_version", "1")),
    )


def workflow_to_row(value: WorkflowRun) -> models.WorkflowRunRow:
    return models.WorkflowRunRow(
        run_id=str(value.run_id),
        workflow_name=value.workflow_name,
        workflow_version=value.workflow_version,
        definition_fingerprint=value.definition_fingerprint,
        plan_fingerprint=value.plan_fingerprint,
        correlation_json=correlation_to_json(value.correlation),
        status=value.status.value,
        created_at=value.created_at,
        started_at=value.started_at,
        ended_at=value.ended_at,
        failure_json=failure_to_json(value.failure),
    )


def workflow_from_row(value: models.WorkflowRunRow) -> WorkflowRun:
    return WorkflowRun(
        run_id=WorkflowRunId.parse(value.run_id),
        workflow_name=value.workflow_name,
        workflow_version=value.workflow_version,
        definition_fingerprint=value.definition_fingerprint,
        plan_fingerprint=value.plan_fingerprint,
        correlation=correlation_from_json(value.correlation_json),
        created_at=value.created_at,
        _status=WorkflowRunStatus(value.status),
        started_at=value.started_at,
        ended_at=value.ended_at,
        failure=failure_from_json(value.failure_json),
    )


def apply_workflow_row(target: models.WorkflowRunRow, value: WorkflowRun) -> None:
    target.status = value.status.value
    target.started_at = value.started_at
    target.ended_at = value.ended_at
    target.failure_json = failure_to_json(value.failure)


def task_run_to_row(value: TaskRun) -> models.TaskRunRow:
    return models.TaskRunRow(
        task_run_id=str(value.task_run_id),
        workflow_run_id=str(value.workflow_run_id),
        task_key=value.task_key,
        status=value.status.value,
        created_at=value.created_at,
        started_at=value.started_at,
        ended_at=value.ended_at,
        skip_reason=value.skip_reason.value if value.skip_reason is not None else None,
        block_reason=value.block_reason.value if value.block_reason is not None else None,
        failure_json=failure_to_json(value.failure),
    )


def task_run_from_row(value: models.TaskRunRow) -> TaskRun:
    return TaskRun(
        task_run_id=TaskRunId.parse(value.task_run_id),
        workflow_run_id=WorkflowRunId.parse(value.workflow_run_id),
        task_key=value.task_key,
        created_at=value.created_at,
        _status=TaskRunStatus(value.status),
        started_at=value.started_at,
        ended_at=value.ended_at,
        skip_reason=SkipReason(value.skip_reason) if value.skip_reason is not None else None,
        block_reason=BlockReason(value.block_reason) if value.block_reason is not None else None,
        failure=failure_from_json(value.failure_json),
    )


def apply_task_run_row(target: models.TaskRunRow, value: TaskRun) -> None:
    target.status = value.status.value
    target.started_at = value.started_at
    target.ended_at = value.ended_at
    target.skip_reason = value.skip_reason.value if value.skip_reason is not None else None
    target.block_reason = value.block_reason.value if value.block_reason is not None else None
    target.failure_json = failure_to_json(value.failure)


def attempt_to_row(value: TaskAttempt) -> models.TaskAttemptRow:
    return models.TaskAttemptRow(
        attempt_id=str(value.attempt_id),
        task_run_id=str(value.task_run_id),
        attempt_number=value.attempt_number,
        status=value.status.value,
        created_at=value.created_at,
        started_at=value.started_at,
        ended_at=value.ended_at,
        failure_json=failure_to_json(value.failure),
    )


def attempt_from_row(value: models.TaskAttemptRow) -> TaskAttempt:
    return TaskAttempt(
        attempt_id=TaskAttemptId.parse(value.attempt_id),
        task_run_id=TaskRunId.parse(value.task_run_id),
        attempt_number=value.attempt_number,
        created_at=value.created_at,
        _status=TaskAttemptStatus(value.status),
        started_at=value.started_at,
        ended_at=value.ended_at,
        failure=failure_from_json(value.failure_json),
    )


def apply_attempt_row(target: models.TaskAttemptRow, value: TaskAttempt) -> None:
    target.status = value.status.value
    target.started_at = value.started_at
    target.ended_at = value.ended_at
    target.failure_json = failure_to_json(value.failure)


def external_ref_to_row(
    *,
    attempt_id: TaskAttemptId,
    value: ExternalRunRef,
) -> models.ExternalRunRefRow:
    return models.ExternalRunRefRow(
        attempt_id=str(attempt_id),
        provider=value.provider,
        kind=value.kind,
        external_run_id=value.external_run_id,
        status_hint=value.status_hint,
        status_locator=value.status_locator,
        correlation_id=(
            str(value.correlation_id) if value.correlation_id is not None else None
        ),
        causation_id=value.causation_id,
        metadata_json=_pairs_to_json(value.metadata),
        namespace=value.namespace,
        contract_version=value.contract_version,
    )


def external_ref_from_row(value: models.ExternalRunRefRow) -> ExternalRunRef:
    correlation_id = value.correlation_id
    return ExternalRunRef(
        provider=value.provider,
        external_run_id=value.external_run_id,
        kind=value.kind,
        status_hint=value.status_hint,
        status_locator=value.status_locator,
        correlation_id=(
            CorrelationId.parse(correlation_id) if correlation_id is not None else None
        ),
        causation_id=value.causation_id,
        metadata=_pairs_from_json(value.metadata_json),
        namespace=value.namespace,
        contract_version=value.contract_version,
    )


def transition_from_row(value: models.StateTransitionRow) -> StateTransitionRecord:
    return StateTransitionRecord(
        sequence=value.sequence,
        entity_type=StateEntityType(value.entity_type),
        entity_id=value.entity_id,
        from_status=value.from_status,
        to_status=value.to_status,
        occurred_at=value.occurred_at,
    )


def manifest_from_row(value: models.ManifestReferenceRow) -> ManifestReference:
    return ManifestReference(
        locator=value.locator,
        schema_version=value.schema_version,
        digest=value.digest,
    )


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("persisted optional text value must be a string")
    return value


__all__ = [
    "apply_attempt_row",
    "apply_task_run_row",
    "apply_workflow_row",
    "attempt_from_row",
    "attempt_to_row",
    "correlation_from_json",
    "correlation_to_json",
    "external_ref_from_row",
    "external_ref_to_row",
    "failure_from_json",
    "failure_to_json",
    "manifest_from_row",
    "task_run_from_row",
    "task_run_to_row",
    "transition_from_row",
    "workflow_from_row",
    "workflow_to_row",
]
