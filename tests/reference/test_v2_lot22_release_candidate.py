"""LOT-22 PyWorkflowKit 2.0 release-candidate freeze acceptance."""

from __future__ import annotations

import json
from importlib.metadata import version

import pyworkflowkit
from pyworkflowkit import authoring, planning, policies, runtime
from pyworkflowkit._architecture import V2_ROOT_TARGET_ALLOWLIST
from pyworkflowkit.contracts.v2_release_candidate import (
    V2_RC_CHANGE_POLICY,
    V2_RELEASE_CANDIDATE_TARGET_RELEASE,
    V2_RELEASE_CANDIDATE_VERSION,
    V2_STABLE_IDENTITIES,
    V2_STABLE_PROTOCOLS,
    V2_SUPPORTED_PYTHON_VERSIONS,
    v2_release_candidate_evidence_manifest,
)
from pyworkflowkit.executors.contracts import (
    V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS,
    V2_EXECUTOR_PROTOCOL_METHODS,
)
from pyworkflowkit.persistence.contracts import V2_METADATA_STORE_METHODS
from pyworkflowkit.public_api import (
    PUBLIC_API_TARGET_RELEASE,
    V2_PUBLIC_API_TARGET_RELEASE,
    v2_root_public_api_snapshot,
)
from pyworkflowkit.runtime import (
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)


def test_lot22_candidate_identity_remains_frozen_after_stable_promotion() -> None:
    assert V2_RELEASE_CANDIDATE_VERSION == "2.0.0rc1"
    assert V2_RELEASE_CANDIDATE_TARGET_RELEASE == "2.0.0"
    assert V2_PUBLIC_API_TARGET_RELEASE == "2.0.0"
    assert pyworkflowkit.__version__ in {"2.0.0rc1", "2.0.0", "2.1.0rc1", "2.1.0"}
    assert version("pyworkflowkit") == pyworkflowkit.__version__


def test_lot22_root_is_exact_canonical_v2_allowlist() -> None:
    assert tuple(pyworkflowkit.__all__) == V2_ROOT_TARGET_ALLOWLIST
    assert v2_root_public_api_snapshot()["exports"] == list(V2_ROOT_TARGET_ALLOWLIST)

    assert pyworkflowkit.WorkflowDefinition is authoring.WorkflowDefinition
    assert pyworkflowkit.TaskDefinition is authoring.TaskDefinition
    assert pyworkflowkit.ExecutionPlan is planning.ExecutionPlan
    assert pyworkflowkit.RetryPolicy is policies.RetryPolicy
    assert pyworkflowkit.TimeoutPolicy is policies.TimeoutPolicy
    assert pyworkflowkit.WorkflowRuntime is runtime.WorkflowRuntime
    assert pyworkflowkit.WorkflowResult is runtime.WorkflowResult
    assert pyworkflowkit.WorkflowRun is runtime.WorkflowRun
    assert pyworkflowkit.TaskRun is runtime.TaskRun
    assert pyworkflowkit.TaskAttempt is runtime.TaskAttempt

    legacy_only = {
        "RunContext",
        "TaskResult",
        "TaskHandle",
        "WorkflowBuilder",
        "WorkflowParameter",
    }
    assert legacy_only.isdisjoint(pyworkflowkit.__all__)


def test_lot22_historical_1_0_api_snapshot_remains_migration_evidence() -> None:
    assert PUBLIC_API_TARGET_RELEASE == "1.0.0"
    assert PUBLIC_API_TARGET_RELEASE != V2_PUBLIC_API_TARGET_RELEASE


def test_lot22_execution_identities_are_distinct_and_frozen() -> None:
    assert V2_STABLE_IDENTITIES == (
        "CorrelationId",
        "WorkflowRunId",
        "TaskRunId",
        "TaskAttemptId",
    )

    values = (
        CorrelationId.parse("same"),
        WorkflowRunId.parse("same"),
        TaskRunId.parse("same"),
        TaskAttemptId.parse("same"),
    )
    assert len({type(value) for value in values}) == 4
    assert all(str(value) == "same" for value in values)


def test_lot22_protocol_member_sets_are_frozen() -> None:
    assert V2_STABLE_PROTOCOLS["Executor"] == V2_EXECUTOR_PROTOCOL_METHODS
    assert V2_STABLE_PROTOCOLS["CancellableExecutor"] == V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS
    assert V2_STABLE_PROTOCOLS["MetadataStore"] == V2_METADATA_STORE_METHODS
    assert V2_STABLE_PROTOCOLS["WorkloadDescriptor"] == (
        "workload_kind",
        "portability",
        "fingerprint_payload",
    )
    assert V2_STABLE_PROTOCOLS["ExternalRunVerifier"] == ("provider", "verify")
    assert V2_STABLE_PROTOCOLS["V2RuntimeEventSink"] == ("name", "emit")


def test_lot22_manifest_composes_every_v2_freeze_contract() -> None:
    manifest = v2_release_candidate_evidence_manifest()

    assert manifest["candidate_version"] == V2_RELEASE_CANDIDATE_VERSION
    assert manifest["target_release"] == V2_RELEASE_CANDIDATE_TARGET_RELEASE
    assert manifest["package_version"] == pyworkflowkit.__version__
    assert manifest["supported_python_versions"] == list(V2_SUPPORTED_PYTHON_VERSIONS)
    assert manifest["change_policy"] == V2_RC_CHANGE_POLICY
    assert manifest["architecture_redesign_permitted"] is False

    contracts = manifest["contracts"]
    assert isinstance(contracts, dict)
    assert tuple(sorted(contracts)) == (
        "architecture",
        "authoring",
        "executor",
        "metadata_store",
        "migration",
        "planning",
        "plugins",
        "pyingestkit",
        "pytransformkit",
        "retry",
        "root_api",
        "runtime",
        "states",
        "timeout",
        "wire",
    )
    assert contracts["root_api"] == v2_root_public_api_snapshot()
    assert contracts["architecture"]["target_release"] == "2.0.0"
    assert contracts["states"]["contract_version"] == "1"
    assert contracts["executor"]["contract_version"] == "4"
    assert contracts["metadata_store"]["contract_version"] == "2"
    assert contracts["plugins"]["plugin_api_version"] == "2"
    assert contracts["migration"]["direction"] == "v1_to_v2_only"


def test_lot22_release_evidence_manifest_is_deterministic_json() -> None:
    first = v2_release_candidate_evidence_manifest()
    second = v2_release_candidate_evidence_manifest()

    assert first == second
    encoded = json.dumps(first, allow_nan=False, sort_keys=True)
    assert json.loads(encoded) == first


def test_lot22_rc_policy_allows_only_blocker_fixes_without_reset() -> None:
    manifest = v2_release_candidate_evidence_manifest()

    assert V2_RC_CHANGE_POLICY == "blocker-fixes-only-without-rc-reset"
    assert manifest["architecture_redesign_permitted"] is False
    assert "release-evidence-manifest" in manifest["required_qualification_families"]
