"""Explicit PyWorkflowKit 1.1 -> V2 semantic migration helpers.

This module is migration-only. Canonical V2 modules must never depend on it.

The migration is intentionally evidence preserving: values that did not exist in the
legacy model are never synthesized. Callers must provide missing V2 evidence explicitly
or migration fails closed with :class:`V1MigrationEvidenceError`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pyworkflowkit.authoring import (
    RegisteredWorkload,
    TaskDefinition as V2TaskDefinition,
    WorkflowDefinition as V2WorkflowDefinition,
)
from pyworkflowkit.diagnostics import FailureCategory
from pyworkflowkit.domain.definitions import (
    TaskDefinition as V1TaskDefinition,
    WorkflowDefinition as V1WorkflowDefinition,
)
from pyworkflowkit.domain.enums import (
    TaskAttemptStatus as V1TaskAttemptStatus,
    TaskRunStatus as V1TaskRunStatus,
    TimeoutMode,
    WorkflowRunStatus as V1WorkflowRunStatus,
)
from pyworkflowkit.domain.runtime import (
    TaskAttempt as V1TaskAttempt,
    TaskRun as V1TaskRun,
    WorkflowRun as V1WorkflowRun,
)
from pyworkflowkit.domain.values import ExternalRunRef as V1ExternalRunRef
from pyworkflowkit.policies import RetryPolicy as V2RetryPolicy
from pyworkflowkit.policies import TimeoutPolicy
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    ExternalRunRef as V2ExternalRunRef,
    TaskAttempt as V2TaskAttempt,
    TaskAttemptId,
    TaskRun as V2TaskRun,
    TaskRunId,
    WorkflowRun as V2WorkflowRun,
    WorkflowRunId,
)
from pyworkflowkit.states import (
    SkipReason as V2SkipReason,
    TaskAttemptStatus as V2TaskAttemptStatus,
    TaskRunStatus as V2TaskRunStatus,
    WorkflowRunStatus as V2WorkflowRunStatus,
)

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
        "external_run_kind_requires_explicit_input": True,
        "legacy_failure_fields_preserved_as_evidence": True,
        "legacy_retry_eligible_at_preserved_as_evidence": True,
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
    "V1MigrationError",
    "V1MigrationEvidenceError",
    "V1MigrationUnsupportedError",
    "V1_TO_V2_MIGRATION_CONTRACT_VERSION",
    "WorkflowRunMigrationContext",
    "migrate_external_run_ref",
    "migrate_task_attempt",
    "migrate_task_definition",
    "migrate_task_run",
    "migrate_workflow_definition",
    "migrate_workflow_run",
    "migration_contract_snapshot",
]
