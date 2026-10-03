"""V2 recovery reconciliation for persisted ambiguous runtime work."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.diagnostics.recovery import RecoveryAssessment, RecoveryInspector
from pyworkflowkit.errors import DuplicateReconciliationVerifierError
from pyworkflowkit.persistence import MetadataStore
from pyworkflowkit.runtime.entities import TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId
from pyworkflowkit.runtime.references import ExternalRunRef
from pyworkflowkit.runtime.services import Clock, SystemClock
from pyworkflowkit.states import (
    TaskAttemptStateMachine,
    TaskAttemptStatus,
    TaskRunStateMachine,
    TaskRunStatus,
    WorkflowRunStateMachine,
    WorkflowRunStatus,
)
from pyworkflowkit.states.enums import (
    TASK_ATTEMPT_TERMINAL_STATUSES,
    TASK_RUN_TERMINAL_STATUSES,
    WORKFLOW_TERMINAL_STATUSES,
)


class ExternalRunStatus(StrEnum):
    """Provider-neutral external execution status used during reconciliation."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    NOT_FOUND = "not_found"
    UNKNOWN = "unknown"


@runtime_checkable
class ExternalRunVerifier(Protocol):
    """Provider adapter capable of observing one ExternalRunRef."""

    @property
    def provider(self) -> str:
        """Provider key handled by this verifier."""

    def verify(self, external_ref: ExternalRunRef) -> ExternalRunStatus:
        """Observe current provider truth without mutating the external execution."""


class ReconciliationDisposition(StrEnum):
    """Result of reconciling one persisted TaskRun."""

    NO_ACTION = "no_action"
    RESOLVED_SUCCEEDED = "resolved_succeeded"
    RESOLVED_FAILED = "resolved_failed"
    RESOLVED_CANCELLED = "resolved_cancelled"
    RESOLVED_TIMED_OUT = "resolved_timed_out"
    STILL_RUNNING = "still_running"
    MANUAL_REQUIRED = "manual_required"


@dataclass(frozen=True, slots=True)
class ExternalRunObservation:
    """Normalized provider observation with secret-safe failure reporting."""

    provider: str
    kind: str
    external_run_id: str
    status: ExternalRunStatus
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class TaskReconciliation:
    """Reconciliation result for one TaskRun."""

    task_run_id: TaskRunId
    task_key: str
    attempt_id: TaskAttemptId | None
    disposition: ReconciliationDisposition
    observations: tuple[ExternalRunObservation, ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    """Result of one recovery/reconciliation pass."""

    workflow_run_id: WorkflowRunId
    workflow_status_before: WorkflowRunStatus
    workflow_status_after: WorkflowRunStatus
    assessment: RecoveryAssessment
    task_reconciliations: tuple[TaskReconciliation, ...]

    @property
    def fully_resolved(self) -> bool:
        return all(
            item.disposition
            not in {
                ReconciliationDisposition.STILL_RUNNING,
                ReconciliationDisposition.MANUAL_REQUIRED,
            }
            for item in self.task_reconciliations
        )

    @property
    def requires_manual_action(self) -> bool:
        return any(
            item.disposition is ReconciliationDisposition.MANUAL_REQUIRED
            for item in self.task_reconciliations
        )

    @property
    def has_still_running(self) -> bool:
        return any(
            item.disposition is ReconciliationDisposition.STILL_RUNNING
            for item in self.task_reconciliations
        )


class ExternalRunVerifierRegistry:
    """Explicit provider → verifier registry."""

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
    """Resolve persisted runtime ambiguity from local and provider evidence."""

    def __init__(
        self,
        *,
        metadata: MetadataStore,
        verifier_registry: ExternalRunVerifierRegistry | None = None,
        clock: Clock | None = None,
    ) -> None:
        if not isinstance(metadata, MetadataStore):
            raise TypeError("metadata must satisfy the V2 MetadataStore Protocol")
        self._metadata = metadata
        self._verifiers = verifier_registry or ExternalRunVerifierRegistry()
        self._clock = clock or SystemClock()
        self._recovery = RecoveryInspector(metadata=metadata)
        self._workflow_states = WorkflowRunStateMachine()
        self._task_states = TaskRunStateMachine()
        self._attempt_states = TaskAttemptStateMachine()

    @property
    def verifier_registry(self) -> ExternalRunVerifierRegistry:
        return self._verifiers

    def assess(self, workflow_run_id: WorkflowRunId) -> RecoveryAssessment:
        return self._recovery.assess(workflow_run_id)

    def discover(self) -> tuple[RecoveryAssessment, ...]:
        return self._recovery.discover()

    def reconcile(self, workflow_run_id: WorkflowRunId) -> ReconciliationReport:
        assessment = self._recovery.assess(workflow_run_id)
        run_before = self._metadata.get_workflow_run(workflow_run_id)
        before_status = run_before.status

        if run_before.status in WORKFLOW_TERMINAL_STATUSES:
            return ReconciliationReport(
                workflow_run_id=workflow_run_id,
                workflow_status_before=before_status,
                workflow_status_after=before_status,
                assessment=assessment,
                task_reconciliations=(),
            )

        reconciliations = tuple(
            self._reconcile_task(task_run.task_run_id)
            for task_run in self._metadata.list_task_runs(workflow_run_id)
            if task_run.status not in TASK_RUN_TERMINAL_STATUSES
        )

        unresolved = any(
            item.disposition
            in {
                ReconciliationDisposition.STILL_RUNNING,
                ReconciliationDisposition.MANUAL_REQUIRED,
            }
            for item in reconciliations
        )
        if not unresolved:
            self._reconcile_workflow(workflow_run_id)

        run_after = self._metadata.get_workflow_run(workflow_run_id)
        return ReconciliationReport(
            workflow_run_id=workflow_run_id,
            workflow_status_before=before_status,
            workflow_status_after=run_after.status,
            assessment=assessment,
            task_reconciliations=reconciliations,
        )

    def _reconcile_task(self, task_run_id: TaskRunId) -> TaskReconciliation:
        task_run = self._metadata.get_task_run(task_run_id)
        attempts = self._metadata.list_task_attempts(task_run_id)
        if not attempts:
            return TaskReconciliation(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                attempt_id=None,
                disposition=ReconciliationDisposition.NO_ACTION,
                reasons=("task_has_not_started_an_attempt",),
            )

        attempt = attempts[-1]
        if attempt.status in TASK_ATTEMPT_TERMINAL_STATUSES:
            disposition = self._repair_task_from_terminal_attempt(task_run, attempt)
            return TaskReconciliation(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                attempt_id=attempt.attempt_id,
                disposition=disposition,
                reasons=("terminal_attempt_is_durable_authority",),
            )

        refs = self._metadata.list_external_run_refs(attempt.attempt_id)
        if not refs:
            return TaskReconciliation(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                attempt_id=attempt.attempt_id,
                disposition=ReconciliationDisposition.MANUAL_REQUIRED,
                reasons=("no_external_reconciliation_evidence",),
            )

        observations = tuple(self._observe(ref) for ref in refs)
        statuses = {item.status for item in observations}

        if any(
            status in {ExternalRunStatus.UNKNOWN, ExternalRunStatus.NOT_FOUND}
            for status in statuses
        ):
            return TaskReconciliation(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                attempt_id=attempt.attempt_id,
                disposition=ReconciliationDisposition.MANUAL_REQUIRED,
                observations=observations,
                reasons=("external_status_is_not_conclusive",),
            )

        if len(statuses) != 1:
            return TaskReconciliation(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                attempt_id=attempt.attempt_id,
                disposition=ReconciliationDisposition.MANUAL_REQUIRED,
                observations=observations,
                reasons=("conflicting_external_statuses",),
            )

        status = next(iter(statuses))
        if status is ExternalRunStatus.RUNNING:
            return TaskReconciliation(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                attempt_id=attempt.attempt_id,
                disposition=ReconciliationDisposition.STILL_RUNNING,
                observations=observations,
                reasons=("external_execution_is_still_running",),
            )

        external_ref = refs[0]
        if status is ExternalRunStatus.SUCCEEDED:
            self._resolve_attempt_and_task(
                task_run=task_run,
                attempt=attempt,
                attempt_status=TaskAttemptStatus.SUCCEEDED,
                task_status=TaskRunStatus.SUCCEEDED,
                failure=None,
            )
            disposition = ReconciliationDisposition.RESOLVED_SUCCEEDED
        elif status is ExternalRunStatus.FAILED:
            failure = self._reconciled_failure(
                task_run=task_run,
                attempt=attempt,
                external_ref=external_ref,
                cancelled=False,
            )
            self._resolve_attempt_and_task(
                task_run=task_run,
                attempt=attempt,
                attempt_status=TaskAttemptStatus.FAILED,
                task_status=TaskRunStatus.FAILED,
                failure=failure,
            )
            disposition = ReconciliationDisposition.RESOLVED_FAILED
        elif status is ExternalRunStatus.CANCELLED:
            failure = self._reconciled_failure(
                task_run=task_run,
                attempt=attempt,
                external_ref=external_ref,
                cancelled=True,
            )
            self._resolve_attempt_and_task(
                task_run=task_run,
                attempt=attempt,
                attempt_status=TaskAttemptStatus.CANCELLED,
                task_status=TaskRunStatus.CANCELLED,
                failure=failure,
            )
            disposition = ReconciliationDisposition.RESOLVED_CANCELLED
        else:  # pragma: no cover - enum exhaustiveness guard
            return TaskReconciliation(
                task_run_id=task_run.task_run_id,
                task_key=task_run.task_key,
                attempt_id=attempt.attempt_id,
                disposition=ReconciliationDisposition.MANUAL_REQUIRED,
                observations=observations,
                reasons=("unsupported_external_status",),
            )

        return TaskReconciliation(
            task_run_id=task_run.task_run_id,
            task_key=task_run.task_key,
            attempt_id=attempt.attempt_id,
            disposition=disposition,
            observations=observations,
            reasons=("provider_truth_applied_to_same_task_attempt",),
        )

    def _observe(self, external_ref: ExternalRunRef) -> ExternalRunObservation:
        verifier = self._verifiers.resolve(external_ref.provider)
        if verifier is None:
            return ExternalRunObservation(
                provider=external_ref.provider,
                kind=external_ref.kind,
                external_run_id=external_ref.external_run_id,
                status=ExternalRunStatus.UNKNOWN,
                reason="verifier_not_registered",
            )
        try:
            status = verifier.verify(external_ref)
        except Exception as exc:
            return ExternalRunObservation(
                provider=external_ref.provider,
                kind=external_ref.kind,
                external_run_id=external_ref.external_run_id,
                status=ExternalRunStatus.UNKNOWN,
                reason=f"verification_failed:{type(exc).__name__}",
            )
        if not isinstance(status, ExternalRunStatus):
            return ExternalRunObservation(
                provider=external_ref.provider,
                kind=external_ref.kind,
                external_run_id=external_ref.external_run_id,
                status=ExternalRunStatus.UNKNOWN,
                reason="verifier_returned_invalid_status",
            )
        return ExternalRunObservation(
            provider=external_ref.provider,
            kind=external_ref.kind,
            external_run_id=external_ref.external_run_id,
            status=status,
        )

    def _repair_task_from_terminal_attempt(
        self,
        task_run: TaskRun,
        attempt: TaskAttempt,
    ) -> ReconciliationDisposition:
        mapping = {
            TaskAttemptStatus.SUCCEEDED: (
                TaskRunStatus.SUCCEEDED,
                ReconciliationDisposition.RESOLVED_SUCCEEDED,
            ),
            TaskAttemptStatus.FAILED: (
                TaskRunStatus.FAILED,
                ReconciliationDisposition.RESOLVED_FAILED,
            ),
            TaskAttemptStatus.CANCELLED: (
                TaskRunStatus.CANCELLED,
                ReconciliationDisposition.RESOLVED_CANCELLED,
            ),
            TaskAttemptStatus.TIMED_OUT: (
                TaskRunStatus.TIMED_OUT,
                ReconciliationDisposition.RESOLVED_TIMED_OUT,
            ),
        }
        task_status, disposition = mapping[attempt.status]
        self._transition_task(task_run, task_status, failure=attempt.failure)
        return disposition

    def _resolve_attempt_and_task(
        self,
        *,
        task_run: TaskRun,
        attempt: TaskAttempt,
        attempt_status: TaskAttemptStatus,
        task_status: TaskRunStatus,
        failure: FailureEvidence | None,
    ) -> None:
        if attempt.status is not attempt_status:
            self._transition_attempt(attempt, attempt_status, failure=failure)
        task_run = self._metadata.get_task_run(task_run.task_run_id)
        if task_run.status is not task_status:
            self._transition_task(task_run, task_status, failure=failure)

    def _reconcile_workflow(self, workflow_run_id: WorkflowRunId) -> None:
        run = self._metadata.get_workflow_run(workflow_run_id)
        if run.status in WORKFLOW_TERMINAL_STATUSES:
            return

        task_runs = self._metadata.list_task_runs(workflow_run_id)
        statuses = {task_run.status for task_run in task_runs}

        if any(status is TaskRunStatus.UNKNOWN_OUTCOME for status in statuses):
            return
        if any(status is TaskRunStatus.FAILED for status in statuses):
            self._transition_workflow(
                run,
                WorkflowRunStatus.FAILED,
                failure=_first_task_failure(task_runs),
            )
            return
        if any(status is TaskRunStatus.TIMED_OUT for status in statuses):
            self._transition_workflow(
                run,
                WorkflowRunStatus.TIMED_OUT,
                failure=_first_task_failure(task_runs),
            )
            return
        if any(status is TaskRunStatus.CANCELLED for status in statuses):
            self._transition_workflow(
                run,
                WorkflowRunStatus.CANCELLED,
                failure=_first_task_failure(task_runs),
            )
            return
        if task_runs and all(status in TASK_RUN_TERMINAL_STATUSES for status in statuses):
            self._transition_workflow(run, WorkflowRunStatus.SUCCEEDED)
            return
        if run.status is WorkflowRunStatus.UNKNOWN_OUTCOME:
            self._transition_workflow(run, WorkflowRunStatus.RUNNING)

    def _reconciled_failure(
        self,
        *,
        task_run: TaskRun,
        attempt: TaskAttempt,
        external_ref: ExternalRunRef,
        cancelled: bool,
    ) -> FailureEvidence:
        run = self._metadata.get_workflow_run(task_run.workflow_run_id)
        return FailureEvidence(
            error_code=(
                "PWK-RECONCILED-EXTERNAL-CANCELLED"
                if cancelled
                else "PWK-RECONCILED-EXTERNAL-FAILED"
            ),
            category=(
                FailureCategory.CANCELLED
                if cancelled
                else FailureCategory.EXTERNAL_PROVIDER
            ),
            retryability=(
                Retryability.NON_RETRYABLE if cancelled else Retryability.UNKNOWN
            ),
            uncertainty=OutcomeUncertainty.KNOWN,
            correlation_id=run.correlation.correlation_id,
            workflow_run_id=str(run.run_id),
            task_run_id=str(task_run.task_run_id),
            task_attempt_id=str(attempt.attempt_id),
            external_run=external_ref,
            source_component="workflow_runtime.reconciliation",
            message_summary=(
                "external execution cancellation confirmed during reconciliation"
                if cancelled
                else "external execution failure confirmed during reconciliation"
            ),
            occurred_at=self._now(),
            details=(("provider_status_source", "reconciliation_verifier"),),
        )

    def _transition_workflow(
        self,
        run: WorkflowRun,
        target: WorkflowRunStatus,
        *,
        failure: FailureEvidence | None = None,
    ) -> None:
        expected = run.status
        at = self._now()
        self._workflow_states.transition(run, target, at=at, failure=failure)
        self._metadata.update_workflow_run(
            run,
            expected_status=expected,
            transitioned_at=at,
        )

    def _transition_task(
        self,
        task_run: TaskRun,
        target: TaskRunStatus,
        *,
        failure: FailureEvidence | None = None,
    ) -> None:
        expected = task_run.status
        at = self._now()
        self._task_states.transition(task_run, target, at=at, failure=failure)
        self._metadata.update_task_run(
            task_run,
            expected_status=expected,
            transitioned_at=at,
        )

    def _transition_attempt(
        self,
        attempt: TaskAttempt,
        target: TaskAttemptStatus,
        *,
        failure: FailureEvidence | None = None,
    ) -> None:
        expected = attempt.status
        at = self._now()
        self._attempt_states.transition(attempt, target, at=at, failure=failure)
        self._metadata.update_task_attempt(
            attempt,
            expected_status=expected,
            transitioned_at=at,
        )

    def _now(self):
        value = self._clock.now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock.now() must return a timezone-aware datetime")
        return value


def _first_task_failure(task_runs: tuple[TaskRun, ...]) -> FailureEvidence | None:
    for task_run in task_runs:
        if task_run.failure is not None:
            return task_run.failure
    return None


__all__ = [
    "ExternalRunObservation",
    "ExternalRunStatus",
    "ExternalRunVerifier",
    "ExternalRunVerifierRegistry",
    "ReconciliationDisposition",
    "ReconciliationReport",
    "ReconciliationService",
    "TaskReconciliation",
]
