"""Explicit PyWorkflowKit 1.1 -> V2 semantic migration helpers.

This module is migration-only. Canonical V2 modules must never depend on it.

The migration is intentionally evidence preserving: values that did not exist in the
legacy model are never synthesized. Callers must provide missing V2 evidence explicitly
or migration fails closed with :class:`V1MigrationEvidenceError`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pyworkflowkit.authoring import RegisteredWorkload
from pyworkflowkit.authoring import TaskDefinition as V2TaskDefinition
from pyworkflowkit.authoring import WorkflowDefinition as V2WorkflowDefinition
from pyworkflowkit.diagnostics import FailureCategory
from pyworkflowkit.domain.definitions import TaskDefinition as V1TaskDefinition
from pyworkflowkit.domain.definitions import WorkflowDefinition as V1WorkflowDefinition
from pyworkflowkit.domain.enums import SkipReason as V1SkipReason
from pyworkflowkit.domain.enums import TaskAttemptStatus as V1TaskAttemptStatus
from pyworkflowkit.domain.enums import TaskRunStatus as V1TaskRunStatus
from pyworkflowkit.domain.enums import TimeoutMode
from pyworkflowkit.domain.enums import WorkflowRunStatus as V1WorkflowRunStatus
from pyworkflowkit.domain.ids import ExternalRunRefId, TaskId, WorkflowId
from pyworkflowkit.domain.ids import TaskAttemptId as V1TaskAttemptId
from pyworkflowkit.domain.ids import TaskRunId as V1TaskRunId
from pyworkflowkit.domain.ids import WorkflowRunId as V1WorkflowRunId
from pyworkflowkit.domain.runtime import TaskAttempt as V1TaskAttempt
from pyworkflowkit.domain.runtime import TaskRun as V1TaskRun
from pyworkflowkit.domain.runtime import WorkflowRun as V1WorkflowRun
from pyworkflowkit.domain.values import ExternalRunRef as V1ExternalRunRef
from pyworkflowkit.policies import RetryPolicy as V2RetryPolicy
from pyworkflowkit.policies import TimeoutPolicy
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.runtime import ExternalRunRef as V2ExternalRunRef
from pyworkflowkit.runtime import TaskAttempt as V2TaskAttempt
from pyworkflowkit.runtime import TaskRun as V2TaskRun
from pyworkflowkit.runtime import WorkflowRun as V2WorkflowRun
from pyworkflowkit.runtime.evidence import normalize_json_value, plain_json_value
from pyworkflowkit.states import SkipReason as V2SkipReason
from pyworkflowkit.states import TaskAttemptStatus as V2TaskAttemptStatus
from pyworkflowkit.states import TaskRunStatus as V2TaskRunStatus
from pyworkflowkit.states import WorkflowRunStatus as V2WorkflowRunStatus

V1_TO_V2_MIGRATION_CONTRACT_VERSION = "1"

_DEFAULT_EXECUTOR_MAP: Mapping[str, str] = {
    "local": "inline",
}


class MigrationDisposition(StrEnum):
    """Outcome classification for one explicit migration operation."""

    MIGRATED = "migrated"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class MigrationIssue:
    """Machine-readable migration issue without inferred remediation."""

    code: str
    disposition: MigrationDisposition
    summary: str
    field: str | None = None

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise ValueError("MigrationIssue code must not be empty")
        if not isinstance(self.disposition, MigrationDisposition):
            raise TypeError("disposition must be a MigrationDisposition")
        if not self.summary or not self.summary.strip():
            raise ValueError("MigrationIssue summary must not be empty")
        if self.field is not None and not self.field.strip():
            raise ValueError("field must not be blank")


class V1MigrationError(ValueError):
    """Base class for explicit 1.1 -> V2 migration failures."""

    def __init__(self, issue: MigrationIssue) -> None:
        self.issue = issue
        super().__init__(f"{issue.code}: {issue.summary}")


class V1MigrationEvidenceError(V1MigrationError):
    """Raised when V2 requires evidence that V1 did not persist."""


class V1MigrationUnsupportedError(V1MigrationError):
    """Raised when preserving a V1 semantic has no qualified V2 mapping."""


@dataclass(frozen=True, slots=True)
class WorkflowRunMigrationContext:
    """Caller-supplied V2 evidence unavailable in the legacy WorkflowRun."""

    definition_fingerprint: str
    plan_fingerprint: str
    correlation: CorrelationContext

    def __post_init__(self) -> None:
        _require_text(self.definition_fingerprint, field_name="definition_fingerprint")
        _require_text(self.plan_fingerprint, field_name="plan_fingerprint")
        if not isinstance(self.correlation, CorrelationContext):
            raise TypeError("correlation must be a CorrelationContext")


@dataclass(frozen=True, slots=True)
class TaskAttemptMigrationContext:
    """Caller-supplied creation timestamp absent from the V1 TaskAttempt entity."""

    created_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.created_at, field_name="created_at")


@dataclass(frozen=True, slots=True)
class LegacyAttemptEvidence:
    """V1 fields intentionally not coerced into V2 FailureEvidence."""

    retry_eligible_at: datetime | None
    error_type: str | None
    error_message: str | None
    error_category: str | None
    error_metadata: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class TaskAttemptMigration:
    """Projected V2 TaskAttempt plus non-representable legacy evidence."""

    attempt: V2TaskAttempt
    legacy_evidence: LegacyAttemptEvidence


@dataclass(frozen=True, slots=True)
class LegacyExternalRunEvidence:
    """Legacy tracking fields with no direct V2 semantic equivalent."""

    external_ref_id: str
    uri: str | None


@dataclass(frozen=True, slots=True)
class ExternalRunMigration:
    """Projected V2 ExternalRunRef plus legacy-only identity/location evidence."""

    external_run: V2ExternalRunRef
    legacy_evidence: LegacyExternalRunEvidence


@dataclass(frozen=True, slots=True)
class V1RuntimeMetadataSnapshot:
    """Strict data-only export of legacy runtime metadata.

    ExternalRunRef values remain unowned because the legacy value object did not carry a
    TaskAttempt identity.
    """

    workflow_run: V1WorkflowRun
    task_runs: tuple[V1TaskRun, ...]
    task_attempts: tuple[V1TaskAttempt, ...]
    external_runs: tuple[V1ExternalRunRef, ...]
    contract_version: str = V1_TO_V2_MIGRATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.workflow_run, V1WorkflowRun):
            raise TypeError("workflow_run must be a V1 WorkflowRun")
        if any(not isinstance(item, V1TaskRun) for item in self.task_runs):
            raise TypeError("task_runs must contain V1 TaskRun values")
        if any(not isinstance(item, V1TaskAttempt) for item in self.task_attempts):
            raise TypeError("task_attempts must contain V1 TaskAttempt values")
        if any(not isinstance(item, V1ExternalRunRef) for item in self.external_runs):
            raise TypeError("external_runs must contain V1 ExternalRunRef values")
        if self.contract_version != V1_TO_V2_MIGRATION_CONTRACT_VERSION:
            raise ValueError(
                f"unsupported V1 runtime metadata contract version {self.contract_version!r}"
            )

    def to_payload(self) -> dict[str, object]:
        """Return a strict JSON-portable semantic snapshot."""

        return {
            "contract": "pyworkflowkit.v1_runtime_metadata",
            "contract_version": self.contract_version,
            "workflow_run": _export_v1_workflow_run(self.workflow_run),
            "task_runs": [
                _export_v1_task_run(item)
                for item in sorted(self.task_runs, key=lambda value: str(value.task_run_id))
            ],
            "task_attempts": [
                _export_v1_task_attempt(item)
                for item in sorted(
                    self.task_attempts,
                    key=lambda value: (str(value.task_run_id), value.attempt_number),
                )
            ],
            "external_runs": [
                _export_v1_external_run(item)
                for item in sorted(
                    self.external_runs,
                    key=lambda value: str(value.external_ref_id),
                )
            ],
            "external_run_attempt_ownership": None,
        }

    def to_json(self) -> str:
        """Encode canonical JSON without executable Python state."""

        return json.dumps(
            self.to_payload(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, payload: str) -> V1RuntimeMetadataSnapshot:
        """Decode the closed migration schema without importing payload-selected types."""

        if not isinstance(payload, str):
            raise TypeError("payload must be a string")
        data = json.loads(payload, object_pairs_hook=_reject_duplicate_pairs)
        if not isinstance(data, dict):
            raise ValueError("V1 runtime metadata payload must be an object")
        expected = {
            "contract",
            "contract_version",
            "workflow_run",
            "task_runs",
            "task_attempts",
            "external_runs",
            "external_run_attempt_ownership",
        }
        if set(data) != expected:
            raise ValueError("V1 runtime metadata payload fields do not match contract")
        if data["contract"] != "pyworkflowkit.v1_runtime_metadata":
            raise ValueError("unsupported V1 runtime metadata contract")
        if data["contract_version"] != V1_TO_V2_MIGRATION_CONTRACT_VERSION:
            raise ValueError("unsupported V1 runtime metadata contract version")
        if data["external_run_attempt_ownership"] is not None:
            raise ValueError(
                "V1 runtime metadata must not invent ExternalRunRef TaskAttempt ownership"
            )
        workflow = _import_v1_workflow_run(_require_object(data["workflow_run"], "workflow_run"))
        task_runs = tuple(
            _import_v1_task_run(_require_object(item, "task_run"))
            for item in _require_list(data["task_runs"], "task_runs")
        )
        attempts = tuple(
            _import_v1_task_attempt(_require_object(item, "task_attempt"))
            for item in _require_list(data["task_attempts"], "task_attempts")
        )
        external_runs = tuple(
            _import_v1_external_run(_require_object(item, "external_run"))
            for item in _require_list(data["external_runs"], "external_runs")
        )
        return cls(
            workflow_run=workflow,
            task_runs=task_runs,
            task_attempts=attempts,
            external_runs=external_runs,
        )


def migrate_workflow_definition(
    value: V1WorkflowDefinition,
    *,
    executor_map: Mapping[str, str] | None = None,
) -> V2WorkflowDefinition:
    """Migrate a V1 workflow definition without preserving ambiguous aliases."""

    if not isinstance(value, V1WorkflowDefinition):
        raise TypeError("value must be a V1 WorkflowDefinition")
    if value.parameters:
        raise V1MigrationUnsupportedError(
            MigrationIssue(
                code="PWK-MIG-V1-WORKFLOW-PARAMETERS",
                disposition=MigrationDisposition.UNSUPPORTED,
                field="parameters",
                summary=(
                    "V1 workflow-level parameters have no automatic V2 authoring "
                    "equivalent; migrate them explicitly into task inputs or application "
                    "configuration"
                ),
            )
        )

    mapping = dict(_DEFAULT_EXECUTOR_MAP)
    if executor_map is not None:
        mapping.update(executor_map)

    tasks = tuple(
        migrate_task_definition(task, executor_map=mapping)
        for task in value.tasks
    )
    metadata: dict[str, object] = {"migration.source_contract": "pyworkflowkit-1.1"}
    if value.description is not None:
        metadata["migration.legacy_description"] = value.description

    return V2WorkflowDefinition(
        name=str(value.workflow_id),
        version=value.version,
        tasks=tasks,
        failure_policy=value.failure_policy,
        metadata=metadata,
    )


def migrate_task_definition(
    value: V1TaskDefinition,
    *,
    executor_map: Mapping[str, str] | None = None,
) -> V2TaskDefinition:
    """Migrate one V1 task into an explicit registry-backed V2 workload."""

    if not isinstance(value, V1TaskDefinition):
        raise TypeError("value must be a V1 TaskDefinition")
    if value.handler_ref is None:
        raise V1MigrationEvidenceError(
            MigrationIssue(
                code="PWK-MIG-V1-HANDLER-REF-MISSING",
                disposition=MigrationDisposition.INSUFFICIENT_EVIDENCE,
                field="handler_ref",
                summary=(
                    "V1 task has no persisted handler_ref; V2 workload identity cannot "
                    "be reconstructed safely"
                ),
            )
        )
    if value.timeout_mode is TimeoutMode.HARD:
        raise V1MigrationUnsupportedError(
            MigrationIssue(
                code="PWK-MIG-V1-HARD-TIMEOUT",
                disposition=MigrationDisposition.UNSUPPORTED,
                field="timeout_mode",
                summary=(
                    "V1 HARD timeout cannot be collapsed into the V2 generic execution "
                    "deadline without changing cancellation semantics"
                ),
            )
        )

    mapping = dict(_DEFAULT_EXECUTOR_MAP)
    if executor_map is not None:
        mapping.update(executor_map)
    executor_key = mapping.get(value.executor_key)
    if executor_key is None:
        raise V1MigrationUnsupportedError(
            MigrationIssue(
                code="PWK-MIG-V1-EXECUTOR",
                disposition=MigrationDisposition.UNSUPPORTED,
                field="executor_key",
                summary=(
                    f"legacy executor {value.executor_key!r} has no explicit V2 mapping"
                ),
            )
        )

    retry_categories = frozenset(
        _map_legacy_retry_category(category)
        for category in value.retry_policy.retryable_error_categories
    )
    retry_policy = V2RetryPolicy(
        max_attempts=value.retry_policy.max_attempts,
        backoff_strategy=value.retry_policy.backoff_strategy,
        initial_delay_seconds=value.retry_policy.delay_seconds,
        max_delay_seconds=value.retry_policy.max_delay_seconds,
        retryable_failure_categories=retry_categories,
        reconciliation_required=True,
    )

    metadata: dict[str, object] = {
        "migration.legacy_task_id": str(value.task_id),
        "migration.legacy_executor_key": value.executor_key,
    }
    if value.description is not None:
        metadata["migration.legacy_description"] = value.description
    if value.tags:
        metadata["migration.legacy_tags"] = sorted(value.tags)

    return V2TaskDefinition(
        key=str(value.task_id),
        workload=RegisteredWorkload(
            registry_key=value.handler_ref,
            executor_key=executor_key,
        ),
        dependencies=tuple(str(item) for item in value.depends_on),
        retry_policy=retry_policy,
        timeout_policy=TimeoutPolicy(execution_timeout=value.timeout_seconds),
        metadata=metadata,
    )


def migrate_workflow_run(
    value: V1WorkflowRun,
    *,
    context: WorkflowRunMigrationContext,
) -> V2WorkflowRun:
    """Project a V1 WorkflowRun only when missing V2 identity evidence is supplied."""

    if not isinstance(value, V1WorkflowRun):
        raise TypeError("value must be a V1 WorkflowRun")
    if not isinstance(context, WorkflowRunMigrationContext):
        raise TypeError("context must be a WorkflowRunMigrationContext")
    if value.created_at is None:
        raise _missing_evidence("created_at", "V1 WorkflowRun has no created_at")

    status = V2WorkflowRunStatus[value.status.name]
    return V2WorkflowRun(
        run_id=WorkflowRunId.parse(str(value.run_id)),
        workflow_name=str(value.workflow_id),
        workflow_version=value.workflow_version,
        definition_fingerprint=context.definition_fingerprint,
        plan_fingerprint=context.plan_fingerprint,
        correlation=context.correlation,
        created_at=value.created_at,
        _status=status,
        started_at=value.started_at,
        ended_at=value.finished_at,
    )


def migrate_task_run(value: V1TaskRun) -> V2TaskRun:
    """Project one legacy TaskRun when its stored timestamps are sufficient."""

    if not isinstance(value, V1TaskRun):
        raise TypeError("value must be a V1 TaskRun")
    if value.created_at is None:
        raise _missing_evidence("created_at", "V1 TaskRun has no created_at")

    skip_reason = (
        V2SkipReason[value.skip_reason.name]
        if value.skip_reason is not None
        else None
    )
    return V2TaskRun(
        task_run_id=TaskRunId.parse(str(value.task_run_id)),
        workflow_run_id=WorkflowRunId.parse(str(value.run_id)),
        task_key=str(value.task_id),
        created_at=value.created_at,
        _status=V2TaskRunStatus[value.status.name],
        started_at=value.started_at,
        ended_at=value.finished_at,
        skip_reason=skip_reason,
    )


def migrate_task_attempt(
    value: V1TaskAttempt,
    *,
    context: TaskAttemptMigrationContext,
) -> TaskAttemptMigration:
    """Project one V1 attempt while preserving legacy failure/retry fields separately."""

    if not isinstance(value, V1TaskAttempt):
        raise TypeError("value must be a V1 TaskAttempt")
    if not isinstance(context, TaskAttemptMigrationContext):
        raise TypeError("context must be a TaskAttemptMigrationContext")

    attempt = V2TaskAttempt(
        attempt_id=TaskAttemptId.parse(str(value.attempt_id)),
        task_run_id=TaskRunId.parse(str(value.task_run_id)),
        attempt_number=value.attempt_number,
        created_at=context.created_at,
        _status=V2TaskAttemptStatus[value.status.name],
        started_at=value.started_at,
        ended_at=value.finished_at,
        failure=None,
    )
    return TaskAttemptMigration(
        attempt=attempt,
        legacy_evidence=LegacyAttemptEvidence(
            retry_eligible_at=value.retry_eligible_at,
            error_type=value.error_type,
            error_message=value.error_message,
            error_category=value.error_category,
            error_metadata=value.error_metadata,
        ),
    )


def migrate_task_attempt_sequence(
    values: tuple[V1TaskAttempt, ...],
    *,
    created_at_by_attempt_id: Mapping[str, datetime],
) -> tuple[TaskAttemptMigration, ...]:
    """Migrate one ordered legacy retry history without inventing attempt timestamps."""

    if not isinstance(values, tuple):
        raise TypeError("values must be a tuple")
    if not values:
        return ()

    task_run_ids = {str(item.task_run_id) for item in values}
    if len(task_run_ids) != 1:
        raise V1MigrationUnsupportedError(
            MigrationIssue(
                code="PWK-MIG-V1-ATTEMPT-SEQUENCE-OWNER",
                disposition=MigrationDisposition.UNSUPPORTED,
                field="task_run_id",
                summary="retry-history migration requires attempts from one TaskRun",
            )
        )

    ordered = tuple(sorted(values, key=lambda item: item.attempt_number))
    expected_numbers = tuple(range(1, len(ordered) + 1))
    actual_numbers = tuple(item.attempt_number for item in ordered)
    if actual_numbers != expected_numbers:
        raise V1MigrationUnsupportedError(
            MigrationIssue(
                code="PWK-MIG-V1-ATTEMPT-SEQUENCE",
                disposition=MigrationDisposition.UNSUPPORTED,
                field="attempt_number",
                summary=(
                    "legacy retry history must contain a contiguous attempt-number "
                    "sequence starting at 1"
                ),
            )
        )

    migrated: list[TaskAttemptMigration] = []
    for item in ordered:
        attempt_id = str(item.attempt_id)
        created_at = created_at_by_attempt_id.get(attempt_id)
        if created_at is None:
            raise _missing_evidence(
                "created_at",
                f"missing creation timestamp for legacy TaskAttempt {attempt_id!r}",
            )
        migrated.append(
            migrate_task_attempt(
                item,
                context=TaskAttemptMigrationContext(created_at=created_at),
            )
        )
    return tuple(migrated)


def migrate_external_run_ref(
    value: V1ExternalRunRef,
    *,
    kind: str,
    correlation_id: CorrelationId | None = None,
    causation_id: str | None = None,
) -> ExternalRunMigration:
    """Project V1 external tracking only when the missing V2 kind is explicit."""

    if not isinstance(value, V1ExternalRunRef):
        raise TypeError("value must be a V1 ExternalRunRef")
    _require_text(kind, field_name="kind")

    metadata: list[tuple[str, str]] = []
    for key, item in value.metadata.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise V1MigrationUnsupportedError(
                MigrationIssue(
                    code="PWK-MIG-V1-EXTERNAL-METADATA",
                    disposition=MigrationDisposition.UNSUPPORTED,
                    field="metadata",
                    summary=(
                        "V1 ExternalRunRef metadata contains non-string values that "
                        "cannot be placed into the V2 portable metadata contract"
                    ),
                )
            )
        metadata.append((key, item))

    return ExternalRunMigration(
        external_run=V2ExternalRunRef(
            provider=value.provider,
            external_run_id=value.external_run_id,
            kind=kind,
            correlation_id=correlation_id,
            causation_id=causation_id,
            metadata=tuple(sorted(metadata)),
        ),
        legacy_evidence=LegacyExternalRunEvidence(
            external_ref_id=str(value.external_ref_id),
            uri=value.uri,
        ),
    )


def export_v1_runtime_metadata(
    *,
    workflow_run: V1WorkflowRun,
    task_runs: tuple[V1TaskRun, ...],
    task_attempts: tuple[V1TaskAttempt, ...],
    external_runs: tuple[V1ExternalRunRef, ...] = (),
) -> V1RuntimeMetadataSnapshot:
    """Build a strict V1 runtime metadata export without inferred ownership."""

    return V1RuntimeMetadataSnapshot(
        workflow_run=workflow_run,
        task_runs=task_runs,
        task_attempts=task_attempts,
        external_runs=external_runs,
    )


def import_v1_runtime_metadata(payload: str) -> V1RuntimeMetadataSnapshot:
    """Decode a strict V1 semantic export."""

    return V1RuntimeMetadataSnapshot.from_json(payload)


def _export_v1_workflow_run(value: V1WorkflowRun) -> dict[str, object]:
    return {
        "run_id": str(value.run_id),
        "workflow_id": str(value.workflow_id),
        "workflow_version": value.workflow_version,
        "status": value.status.value,
        "parameters": _portable_mapping(value.parameters, path="workflow_run.parameters"),
        "created_at": _iso(value.created_at),
        "started_at": _iso(value.started_at),
        "finished_at": _iso(value.finished_at),
    }


def _export_v1_task_run(value: V1TaskRun) -> dict[str, object]:
    return {
        "task_run_id": str(value.task_run_id),
        "run_id": str(value.run_id),
        "task_id": str(value.task_id),
        "status": value.status.value,
        "skip_reason": value.skip_reason.value if value.skip_reason is not None else None,
        "created_at": _iso(value.created_at),
        "started_at": _iso(value.started_at),
        "finished_at": _iso(value.finished_at),
    }


def _export_v1_task_attempt(value: V1TaskAttempt) -> dict[str, object]:
    return {
        "attempt_id": str(value.attempt_id),
        "task_run_id": str(value.task_run_id),
        "attempt_number": value.attempt_number,
        "status": value.status.value,
        "started_at": _iso(value.started_at),
        "finished_at": _iso(value.finished_at),
        "error_type": value.error_type,
        "error_message": value.error_message,
        "error_category": value.error_category,
        "retry_eligible_at": _iso(value.retry_eligible_at),
        "error_metadata": _portable_mapping(
            value.error_metadata,
            path="task_attempt.error_metadata",
        ),
    }


def _export_v1_external_run(value: V1ExternalRunRef) -> dict[str, object]:
    return {
        "external_ref_id": str(value.external_ref_id),
        "provider": value.provider,
        "external_run_id": value.external_run_id,
        "uri": value.uri,
        "metadata": _portable_mapping(value.metadata, path="external_run.metadata"),
    }


def _import_v1_workflow_run(value: Mapping[str, object]) -> V1WorkflowRun:
    _require_fields(
        value,
        {
            "run_id",
            "workflow_id",
            "workflow_version",
            "status",
            "parameters",
            "created_at",
            "started_at",
            "finished_at",
        },
        "workflow_run",
    )
    return V1WorkflowRun(
        run_id=V1WorkflowRunId(_string(value["run_id"], "run_id")),
        workflow_id=WorkflowId(_string(value["workflow_id"], "workflow_id")),
        workflow_version=_string(value["workflow_version"], "workflow_version"),
        status=V1WorkflowRunStatus(_string(value["status"], "status")),
        parameters=_require_object(value["parameters"], "parameters"),
        created_at=_datetime_or_none(value["created_at"], "created_at"),
        started_at=_datetime_or_none(value["started_at"], "started_at"),
        finished_at=_datetime_or_none(value["finished_at"], "finished_at"),
    )


def _import_v1_task_run(value: Mapping[str, object]) -> V1TaskRun:
    _require_fields(
        value,
        {
            "task_run_id",
            "run_id",
            "task_id",
            "status",
            "skip_reason",
            "created_at",
            "started_at",
            "finished_at",
        },
        "task_run",
    )
    skip_value = value["skip_reason"]
    return V1TaskRun(
        task_run_id=V1TaskRunId(_string(value["task_run_id"], "task_run_id")),
        run_id=V1WorkflowRunId(_string(value["run_id"], "run_id")),
        task_id=TaskId(_string(value["task_id"], "task_id")),
        status=V1TaskRunStatus(_string(value["status"], "status")),
        skip_reason=(
            V1SkipReason(_string(skip_value, "skip_reason"))
            if skip_value is not None
            else None
        ),
        created_at=_datetime_or_none(value["created_at"], "created_at"),
        started_at=_datetime_or_none(value["started_at"], "started_at"),
        finished_at=_datetime_or_none(value["finished_at"], "finished_at"),
    )


def _import_v1_task_attempt(value: Mapping[str, object]) -> V1TaskAttempt:
    _require_fields(
        value,
        {
            "attempt_id",
            "task_run_id",
            "attempt_number",
            "status",
            "started_at",
            "finished_at",
            "error_type",
            "error_message",
            "error_category",
            "retry_eligible_at",
            "error_metadata",
        },
        "task_attempt",
    )
    attempt_number = value["attempt_number"]
    if isinstance(attempt_number, bool) or not isinstance(attempt_number, int):
        raise ValueError("attempt_number must be an integer")
    return V1TaskAttempt(
        attempt_id=V1TaskAttemptId(_string(value["attempt_id"], "attempt_id")),
        task_run_id=V1TaskRunId(_string(value["task_run_id"], "task_run_id")),
        attempt_number=attempt_number,
        status=V1TaskAttemptStatus(_string(value["status"], "status")),
        started_at=_datetime_or_none(value["started_at"], "started_at"),
        finished_at=_datetime_or_none(value["finished_at"], "finished_at"),
        error_type=_optional_string(value["error_type"], "error_type"),
        error_message=_optional_string(value["error_message"], "error_message"),
        error_category=_optional_string(value["error_category"], "error_category"),
        retry_eligible_at=_datetime_or_none(
            value["retry_eligible_at"],
            "retry_eligible_at",
        ),
        error_metadata=_require_object(value["error_metadata"], "error_metadata"),
    )


def _import_v1_external_run(value: Mapping[str, object]) -> V1ExternalRunRef:
    _require_fields(
        value,
        {"external_ref_id", "provider", "external_run_id", "uri", "metadata"},
        "external_run",
    )
    return V1ExternalRunRef(
        external_ref_id=ExternalRunRefId(
            _string(value["external_ref_id"], "external_ref_id")
        ),
        provider=_string(value["provider"], "provider"),
        external_run_id=_string(value["external_run_id"], "external_run_id"),
        uri=_optional_string(value["uri"], "uri"),
        metadata=_require_object(value["metadata"], "metadata"),
    )


def _portable_mapping(value: Mapping[str, object], *, path: str) -> dict[str, object]:
    normalized = normalize_json_value(dict(value), path=path)
    portable = plain_json_value(normalized)
    if not isinstance(portable, dict):
        raise TypeError(f"{path} must normalize to an object")
    return portable


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    _require_aware(value, field_name="datetime")
    return value.isoformat()


def _datetime_or_none(value: object, field_name: str) -> datetime | None:
    if value is None:
        return None
    raw = _string(value, field_name)
    parsed = datetime.fromisoformat(raw)
    _require_aware(parsed, field_name=field_name)
    return parsed


def _reject_duplicate_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _require_object(value: object, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{field_name} must be an object with string keys")
    return dict(value)


def _require_list(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return value


def _require_fields(
    value: Mapping[str, object],
    expected: set[str],
    field_name: str,
) -> None:
    if set(value) != expected:
        raise ValueError(f"{field_name} fields do not match migration contract")


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _optional_string(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _string(value, field_name)


def migration_contract_snapshot() -> dict[str, object]:
    """Return the deterministic LOT-21 V1 migration posture."""

    return {
        "contract_version": V1_TO_V2_MIGRATION_CONTRACT_VERSION,
        "namespace": "pyworkflowkit._compat",
        "direction": "v1_to_v2_only",
        "generic_aliases_preserved": False,
        "default_executor_mapping": {"local": "inline"},
        "hard_timeout_automatic_mapping": False,
        "workflow_parameters_automatic_mapping": False,
        "workflow_run_requires_external_fingerprints": True,
        "workflow_run_requires_external_correlation": True,
        "task_attempt_requires_external_created_at": True,
        "retry_history_requires_contiguous_attempt_numbers": True,
        "external_run_kind_requires_explicit_input": True,
        "legacy_failure_fields_preserved_as_evidence": True,
        "legacy_retry_eligible_at_preserved_as_evidence": True,
        "semantic_metadata_export_import": True,
        "semantic_metadata_external_attempt_ownership": None,
        "ambiguous_external_attempt_ownership_invented": False,
    }


def _map_legacy_retry_category(value: str) -> FailureCategory:
    normalized = value.strip().lower()
    for category in FailureCategory:
        if normalized in {category.value.lower(), category.name.lower()}:
            return category
    raise V1MigrationUnsupportedError(
        MigrationIssue(
            code="PWK-MIG-V1-RETRY-CATEGORY",
            disposition=MigrationDisposition.UNSUPPORTED,
            field="retryable_error_categories",
            summary=f"legacy retry category {value!r} has no explicit V2 FailureCategory mapping",
        )
    )


def _missing_evidence(field: str, summary: str) -> V1MigrationEvidenceError:
    return V1MigrationEvidenceError(
        MigrationIssue(
            code="PWK-MIG-V1-MISSING-EVIDENCE",
            disposition=MigrationDisposition.INSUFFICIENT_EVIDENCE,
            field=field,
            summary=summary,
        )
    )


def _require_text(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_aware(value: datetime, *, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


__all__ = [
    "ExternalRunMigration",
    "LegacyAttemptEvidence",
    "LegacyExternalRunEvidence",
    "MigrationDisposition",
    "MigrationIssue",
    "TaskAttemptMigration",
    "TaskAttemptMigrationContext",
    "V1RuntimeMetadataSnapshot",
    "V1MigrationError",
    "V1MigrationEvidenceError",
    "V1MigrationUnsupportedError",
    "V1_TO_V2_MIGRATION_CONTRACT_VERSION",
    "WorkflowRunMigrationContext",
    "export_v1_runtime_metadata",
    "import_v1_runtime_metadata",
    "migrate_external_run_ref",
    "migrate_task_attempt",
    "migrate_task_attempt_sequence",
    "migrate_task_definition",
    "migrate_task_run",
    "migrate_workflow_definition",
    "migrate_workflow_run",
    "migration_contract_snapshot",
]
