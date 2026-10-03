"""LOT-11 reference acceptance for V2 recovery and reconciliation."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.diagnostics as diagnostics
import pyworkflowkit.runtime as runtime
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.persistence import InMemoryMetadataStore


def test_lot11_qualified_surfaces_are_explicit_without_root_migration() -> None:
    assert "RecoveryAssessment" in diagnostics.__all__
    assert "RecoveryDisposition" in diagnostics.__all__
    assert "RecoveryInspector" in diagnostics.__all__
    assert "TaskRecoveryAssessment" in diagnostics.__all__

    assert "ExternalRunStatus" in runtime.__all__
    assert "ExternalRunVerifier" in runtime.__all__
    assert "ExternalRunVerifierRegistry" in runtime.__all__
    assert "ReconciliationDisposition" in runtime.__all__
    assert "ReconciliationReport" in runtime.__all__
    assert "ReconciliationService" in runtime.__all__
    assert "TaskReconciliation" in runtime.__all__

    assert "ReconciliationService" not in pyworkflowkit.__all__
    assert "RecoveryInspector" not in pyworkflowkit.__all__


def test_lot11_workflow_runtime_exposes_recovery_facade() -> None:
    workflow_runtime = runtime.WorkflowRuntime(
        executor=InlineExecutor(),
        metadata=InMemoryMetadataStore(),
    )

    assert workflow_runtime.recovery_candidates() == ()
    assert callable(workflow_runtime.recovery_assessment)
    assert callable(workflow_runtime.register_external_run_verifier)
    assert callable(workflow_runtime.reconcile_run)


def test_lot11_external_status_vocabulary_is_frozen() -> None:
    assert tuple(status.value for status in runtime.ExternalRunStatus) == (
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "not_found",
        "unknown",
    )


def test_lot11_reconciliation_disposition_vocabulary_is_frozen() -> None:
    assert tuple(status.value for status in runtime.ReconciliationDisposition) == (
        "no_action",
        "resolved_succeeded",
        "resolved_failed",
        "resolved_cancelled",
        "resolved_timed_out",
        "still_running",
        "manual_required",
    )
