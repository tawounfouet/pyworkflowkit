"""LOT-09 reference acceptance for external execution evidence."""

from pyworkflowkit.diagnostics import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.executors import (
    V2_EXECUTOR_CONTRACT_VERSION,
    CancellationStatus,
    TaskCancellationResult,
    TaskExecutionResult,
    v2_executor_contract_snapshot,
)
from pyworkflowkit.persistence import V2_METADATA_STORE_METHODS
from pyworkflowkit.runtime import CorrelationId, ExternalRunRef, TaskAttemptId
from pyworkflowkit.runtime.contracts import (
    V2_RUNTIME_MVP_CONTRACT_VERSION,
    v2_runtime_mvp_contract_snapshot,
)


def _external_ref() -> ExternalRunRef:
    return ExternalRunRef(
        provider="reference-provider",
        kind="job",
        external_run_id="EXT-1",
    )


def test_runtime_contract_marks_lot09_active() -> None:
    snapshot = v2_runtime_mvp_contract_snapshot()

    assert snapshot["contract_version"] == V2_RUNTIME_MVP_CONTRACT_VERSION
    assert snapshot["external_run_evidence"] == "attempt_scoped"
    assert snapshot["unknown_outcome_blind_retry"] is False
    assert snapshot["cancellation_external_run_evidence"] is True


def test_executor_contract_marks_external_evidence_active() -> None:
    snapshot = v2_executor_contract_snapshot()

    assert snapshot["contract_version"] == V2_EXECUTOR_CONTRACT_VERSION
    assert snapshot["task_execution_result_external_runs"] is True
    assert snapshot["task_cancellation_result_external_runs"] is True


def test_metadata_contract_exposes_attempt_scoped_external_refs() -> None:
    assert "append_external_run_ref" in V2_METADATA_STORE_METHODS
    assert "list_external_run_refs" in V2_METADATA_STORE_METHODS


def test_executor_results_expose_external_run_evidence() -> None:
    external_ref = _external_ref()

    execution = TaskExecutionResult(external_runs=(external_ref,))
    cancellation = TaskCancellationResult(
        status=CancellationStatus.UNCONFIRMED,
        attempt_id=TaskAttemptId.parse("TA-LOT09"),
        reason="remote_stop_not_confirmed",
        external_runs=(external_ref,),
    )

    assert execution.external_runs == (external_ref,)
    assert cancellation.external_runs == (external_ref,)


def test_failure_evidence_can_identify_uncertain_external_execution() -> None:
    external_ref = _external_ref()
    failure = FailureEvidence(
        error_code="REMOTE-UNKNOWN",
        category=FailureCategory.UNKNOWN_OUTCOME,
        retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
        uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
        correlation_id=CorrelationId.parse("C-LOT09"),
        external_run=external_ref,
    )

    assert failure.external_run == external_ref
