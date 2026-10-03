"""Transverse 0.6.0 recovery-contract qualification."""

from __future__ import annotations

from importlib.resources import files

import pyworkflowkit._compat.v1_root as v1_root
from pyworkflowkit.application.manifest import MANIFEST_SCHEMA_VERSION
from pyworkflowkit.application.reconciliation import ReconciliationDisposition
from pyworkflowkit.application.recovery import RecoveryLiveness, ResumeEligibility
from pyworkflowkit.domain.enums import (
    RuntimeEventType,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.runtime import TaskAttempt
from pyworkflowkit.plugins import PLUGIN_API_VERSION
from pyworkflowkit.ports.reconciliation import ExternalRunStatus

EXPECTED_PUBLIC_API = {
    "ArtifactId",
    "ArtifactReference",
    "BackoffStrategy",
    "ExternalRunRef",
    "ExternalRunRefId",
    "FailurePolicy",
    "PyWorkflowKitError",
    "RetryPolicy",
    "RunContext",
    "RuntimeSettings",
    "TaskDefinition",
    "TaskHandle",
    "TaskId",
    "TaskResult",
    "TimeoutMode",
    "WorkflowBuilder",
    "WorkflowDefinition",
    "WorkflowId",
    "WorkflowParameter",
    "WorkflowRuntime",
    "__version__",
    "task",
    "workflow",
}


def values(enum_type: type) -> tuple[str, ...]:
    return tuple(item.value for item in enum_type)


def test_v0_6_runtime_lifecycle_contract_remains_stable() -> None:
    assert values(WorkflowRunStatus) == (
        "PENDING",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    )
    assert values(TaskRunStatus) == (
        "PENDING",
        "READY",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "SKIPPED",
        "CANCELLED",
    )
    assert values(TaskAttemptStatus) == (
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    )
    assert values(RuntimeEventType) == (
        "WORKFLOW_STARTED",
        "WORKFLOW_SUCCEEDED",
        "WORKFLOW_FAILED",
        "WORKFLOW_CANCELLED",
        "TASK_READY",
        "TASK_STARTED",
        "TASK_RETRYING",
        "TASK_SUCCEEDED",
        "TASK_FAILED",
        "TASK_SKIPPED",
    )


def test_v0_6_retry_wait_is_evidence_not_a_new_task_state() -> None:
    assert "RETRY_WAITING" not in TaskRunStatus.__members__
    assert "RETRYING" not in TaskRunStatus.__members__
    assert "retry_eligible_at" in TaskAttempt.__dataclass_fields__


def test_v0_6_recovery_and_reconciliation_vocabularies_are_frozen() -> None:
    assert values(RecoveryLiveness) == (
        "terminal",
        "active",
        "stale_candidate",
        "unknown",
    )
    assert values(ResumeEligibility) == (
        "not_eligible",
        "eligible",
        "requires_reconciliation",
    )
    assert values(ExternalRunStatus) == (
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "not_found",
        "unknown",
    )
    assert values(ReconciliationDisposition) == (
        "confirmed_succeeded",
        "confirmed_failed",
        "confirmed_cancelled",
        "still_running",
        "manual_required",
    )


def test_v0_6_portable_contract_versions_remain_compatible() -> None:
    assert MANIFEST_SCHEMA_VERSION == "1"
    assert PLUGIN_API_VERSION == "1"


def test_v0_6_package_root_public_api_remains_intentionally_small() -> None:
    assert set(v1_root.__all__) == EXPECTED_PUBLIC_API
    assert "RecoveryInspector" not in v1_root.__all__
    assert "ReconciliationService" not in v1_root.__all__
    assert "ConcurrentRunner" not in v1_root.__all__


def test_v0_6_migration_chain_is_packaged_through_retry_eligibility() -> None:
    versions = files("pyworkflowkit.migrations.versions")
    assert versions.joinpath("0001_runtime_metadata.py").is_file()
    assert versions.joinpath("0002_task_output_checkpoints.py").is_file()
    assert versions.joinpath("0003_retry_eligible_at.py").is_file()
