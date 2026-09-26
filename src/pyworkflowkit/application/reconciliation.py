"""Read-only reconciliation of ambiguous persisted runtime work."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from pyworkflowkit.application.recovery import (
    RecoveryInspector,
    RecoveryLiveness,
)
from pyworkflowkit.application.retry import pending_retry_attempt
from pyworkflowkit.domain.enums import TASK_TERMINAL_STATUSES, TaskAttemptStatus, TaskRunStatus
from pyworkflowkit.domain.ids import WorkflowRunId
from pyworkflowkit.domain.values import ExternalRunRef
from pyworkflowkit.errors import (
    DuplicateReconciliationVerifierError,
    ReconciliationError,
)
from pyworkflowkit.ports.metadata_store import MetadataStore
from pyworkflowkit.ports.reconciliation import ExternalRunStatus, ExternalRunVerifier
from pyworkflowkit.ports.runtime import Clock


class ReconciliationDisposition(StrEnum):
    """Conservative classification of ambiguous task completion."""

    CONFIRMED_SUCCEEDED = "confirmed_succeeded"
    CONFIRMED_FAILED = "confirmed_failed"
    CONFIRMED_CANCELLED = "confirmed_cancelled"
    STILL_RUNNING = "still_running"
    MANUAL_REQUIRED = "manual_required"


@dataclass(frozen=True, slots=True)
class ExternalRunObservation:
    """Normalized evidence obtained from one ExternalRunRef."""

    external_ref_id: str
    provider: str
    external_run_id: str
    status: ExternalRunStatus
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class TaskReconciliation:
    """Read-only reconciliation classification for one non-terminal TaskRun."""

    task_run_id: str
    task_id: str
    disposition: ReconciliationDisposition
    running_attempt_ids: tuple[str, ...]
    observations: tuple[ExternalRunObservation, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    """Read-only reconciliation report for one stale workflow run."""

    run_id: str
    task_reconciliations: tuple[TaskReconciliation, ...]

    @property
    def fully_resolved(self) -> bool:
        return all(
            item.disposition
            in {
                ReconciliationDisposition.CONFIRMED_SUCCEEDED,
                ReconciliationDisposition.CONFIRMED_FAILED,
                ReconciliationDisposition.CONFIRMED_CANCELLED,
            }
            for item in self.task_reconciliations
        )

    @property
    def has_still_running(self) -> bool:
        return any(
            item.disposition is ReconciliationDisposition.STILL_RUNNING
            for item in self.task_reconciliations
        )

    @property
    def requires_manual_action(self) -> bool:
        return any(
            item.disposition is ReconciliationDisposition.MANUAL_REQUIRED
            for item in self.task_reconciliations
        )


class ExternalRunVerifierRegistry:
    """Explicit mapping from ExternalRunRef.provider to verifier."""

    def __init__(self) -> None:
        self._verifiers: dict[str, ExternalRunVerifier] = {}

    def register(self, verifier: ExternalRunVerifier) -> None:
        provider = verifier.provider
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("verifier.provider must be a non-empty string")
        if provider in self._verifiers:
            raise DuplicateReconciliationVerifierError(provider=provider)
        self._verifiers[provider] = verifier

    def resolve(self, provider: str) -> ExternalRunVerifier | None:
        return self._verifiers.get(provider)

    @property
    def providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._verifiers))


class ReconciliationService:
    """Verify ambiguous external work without mutating persisted runtime state."""

    def __init__(
        self,
        *,
        metadata_store: MetadataStore,
        clock: Clock,
        verifier_registry: ExternalRunVerifierRegistry,
        stale_after: timedelta,
    ) -> None:
        self._metadata_store = metadata_store
        self._verifier_registry = verifier_registry
        self._recovery = RecoveryInspector(
            metadata_store=metadata_store,
            clock=clock,
            stale_after=stale_after,
        )

    def reconcile(self, run_id: WorkflowRunId) -> ReconciliationReport:
        """Reconcile ambiguous task completion for one stale run."""

        assessment = self._recovery.assess(run_id)
        if assessment.liveness is not RecoveryLiveness.STALE_CANDIDATE:
            raise ReconciliationError(
                run_id=str(run_id),
                reason=f"run liveness is {assessment.liveness.value}, not stale_candidate",
            )

        task_runs = tuple(self._metadata_store.list_task_runs(run_id))
        reconciliations: list[TaskReconciliation] = []

        for task_run in sorted(task_runs, key=lambda value: str(value.task_id)):
            if task_run.status in TASK_TERMINAL_STATUSES:
                continue

            attempts = tuple(self._metadata_store.list_task_attempts(task_run.task_run_id))
            running_attempt_ids = tuple(
                str(attempt.attempt_id)
                for attempt in attempts
                if attempt.status is TaskAttemptStatus.RUNNING
            )
            external_refs = tuple(self._metadata_store.list_external_run_refs(task_run.task_run_id))

            if (
                task_run.status is TaskRunStatus.RUNNING
                and not running_attempt_ids
                and pending_retry_attempt(attempts) is not None
            ):
                continue

            if task_run.status is not TaskRunStatus.RUNNING and not external_refs:
                continue

            reconciliations.append(
                self._reconcile_task(
                    task_run_id=str(task_run.task_run_id),
                    task_id=str(task_run.task_id),
                    running_attempt_ids=running_attempt_ids,
                    external_refs=external_refs,
                )
            )

        return ReconciliationReport(
            run_id=str(run_id),
            task_reconciliations=tuple(reconciliations),
        )

    def _reconcile_task(
        self,
        *,
        task_run_id: str,
        task_id: str,
        running_attempt_ids: tuple[str, ...],
        external_refs: tuple[ExternalRunRef, ...],
    ) -> TaskReconciliation:
        if not external_refs:
            return TaskReconciliation(
                task_run_id=task_run_id,
                task_id=task_id,
                disposition=ReconciliationDisposition.MANUAL_REQUIRED,
                running_attempt_ids=running_attempt_ids,
                observations=(),
                reasons=("local_running_work_has_no_external_reconciliation_evidence",),
            )

        observations = tuple(self._verify_ref(ref) for ref in external_refs)
        statuses = {item.status for item in observations}

        if any(
            status in {ExternalRunStatus.UNKNOWN, ExternalRunStatus.NOT_FOUND}
            for status in statuses
        ):
            return TaskReconciliation(
                task_run_id=task_run_id,
                task_id=task_id,
                disposition=ReconciliationDisposition.MANUAL_REQUIRED,
                running_attempt_ids=running_attempt_ids,
                observations=observations,
                reasons=("external_status_is_not_conclusive",),
            )

        if len(statuses) != 1:
            return TaskReconciliation(
                task_run_id=task_run_id,
                task_id=task_id,
                disposition=ReconciliationDisposition.MANUAL_REQUIRED,
                running_attempt_ids=running_attempt_ids,
                observations=observations,
                reasons=("conflicting_external_statuses",),
            )

        status = next(iter(statuses))
        disposition = {
            ExternalRunStatus.SUCCEEDED: ReconciliationDisposition.CONFIRMED_SUCCEEDED,
            ExternalRunStatus.FAILED: ReconciliationDisposition.CONFIRMED_FAILED,
            ExternalRunStatus.CANCELLED: ReconciliationDisposition.CONFIRMED_CANCELLED,
            ExternalRunStatus.RUNNING: ReconciliationDisposition.STILL_RUNNING,
        }.get(status)

        if disposition is None:
            return TaskReconciliation(
                task_run_id=task_run_id,
                task_id=task_id,
                disposition=ReconciliationDisposition.MANUAL_REQUIRED,
                running_attempt_ids=running_attempt_ids,
                observations=observations,
                reasons=("external_status_is_not_conclusive",),
            )

        return TaskReconciliation(
            task_run_id=task_run_id,
            task_id=task_id,
            disposition=disposition,
            running_attempt_ids=running_attempt_ids,
            observations=observations,
            reasons=(f"external_status_{status.value}",),
        )

    def _verify_ref(self, external_ref: ExternalRunRef) -> ExternalRunObservation:
        verifier = self._verifier_registry.resolve(external_ref.provider)
        if verifier is None:
            return ExternalRunObservation(
                external_ref_id=str(external_ref.external_ref_id),
                provider=external_ref.provider,
                external_run_id=external_ref.external_run_id,
                status=ExternalRunStatus.UNKNOWN,
                reason="verifier_not_registered",
            )

        try:
            status = verifier.verify(external_ref)
        except Exception as exc:  # verifier boundary: isolate provider failures
            return ExternalRunObservation(
                external_ref_id=str(external_ref.external_ref_id),
                provider=external_ref.provider,
                external_run_id=external_ref.external_run_id,
                status=ExternalRunStatus.UNKNOWN,
                reason=f"verification_failed:{type(exc).__name__}",
            )

        if not isinstance(status, ExternalRunStatus):
            return ExternalRunObservation(
                external_ref_id=str(external_ref.external_ref_id),
                provider=external_ref.provider,
                external_run_id=external_ref.external_run_id,
                status=ExternalRunStatus.UNKNOWN,
                reason="verifier_returned_invalid_status",
            )

        return ExternalRunObservation(
            external_ref_id=str(external_ref.external_ref_id),
            provider=external_ref.provider,
            external_run_id=external_ref.external_run_id,
            status=status,
        )


__all__ = [
    "ExternalRunObservation",
    "ExternalRunVerifierRegistry",
    "ReconciliationDisposition",
    "ReconciliationReport",
    "ReconciliationService",
    "TaskReconciliation",
]
