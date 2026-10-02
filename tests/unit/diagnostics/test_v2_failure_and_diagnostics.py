"""LOT-01 unit tests for structured failure and diagnostic evidence."""

from __future__ import annotations

from pyworkflowkit.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.policies import RetryDecision
from pyworkflowkit.runtime import CorrelationId, ExternalRunRef


def test_failure_evidence_preserves_uncertainty_and_external_identity() -> None:
    external_run = ExternalRunRef(
        provider="pytransformkit",
        external_run_id="T-913",
        kind="transformation_execution",
    )
    failure = FailureEvidence(
        error_code="PWK-EXT-UNKNOWN",
        category=FailureCategory.UNKNOWN_OUTCOME,
        retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
        uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
        correlation_id=CorrelationId.parse("C-42"),
        workflow_run_id="W-42",
        task_run_id="TR-17",
        task_attempt_id="TA-3",
        external_run=external_run,
        source_component="pytransformkit-adapter",
    )

    assert failure.external_run == external_run
    assert failure.uncertainty is OutcomeUncertainty.REQUIRES_RECONCILIATION
    assert failure.retryability is Retryability.RETRYABLE_AFTER_RECONCILIATION
    assert failure.contract_version == "1"


def test_failure_taxonomy_matches_cross_framework_categories() -> None:
    assert FailureCategory.TRANSIENT.value == "transient"
    assert FailureCategory.TIMEOUT.value == "timeout"
    assert FailureCategory.UNKNOWN_OUTCOME.value == "unknown_outcome"
    assert Retryability.UNKNOWN.value == "unknown"


def test_retry_decision_skeleton_has_all_normative_dispositions() -> None:
    assert {decision.value for decision in RetryDecision} == {
        "retry",
        "do_not_retry",
        "reconcile",
        "abort",
        "cancel",
        "escalate",
    }


def test_diagnostic_carries_workflow_attempt_and_decision_context() -> None:
    diagnostic = Diagnostic(
        code="PWK-RETRY-001",
        severity=DiagnosticSeverity.INFO,
        summary="retry deferred until reconciliation",
        details=(("provider", "pytransformkit"),),
        workflow_run_id="W-42",
        task_run_id="TR-17",
        task_attempt_id="TA-3",
        correlation_id=CorrelationId.parse("C-42"),
        decision_context="unknown_outcome",
        related_policy="RetryPolicy",
    )

    assert diagnostic.task_attempt_id == "TA-3"
    assert diagnostic.decision_context == "unknown_outcome"
    assert diagnostic.related_policy == "RetryPolicy"
