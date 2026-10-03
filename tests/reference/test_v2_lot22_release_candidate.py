"""LOT-22 acceptance for the PyWorkflowKit 2.0.0rc1 contract freeze."""

from __future__ import annotations

import json
from importlib import import_module

import pyworkflowkit
from pyworkflowkit import (
    ExecutionPlan,
    RetryPolicy,
    TaskAttempt,
    TaskAttemptId,
    TaskDefinition,
    TaskRun,
    TaskRunId,
    TimeoutPolicy,
    WorkflowDefinition,
    WorkflowResult,
    WorkflowRun,
    WorkflowRunId,
    WorkflowRuntime,
)
from pyworkflowkit._architecture import (
    V2_CANONICAL_PUBLIC_NAMESPACES,
    V2_ROOT_TARGET_ALLOWLIST,
)
from pyworkflowkit._compat.v1_to_v2 import migration_contract_snapshot
from pyworkflowkit.authoring import (
    TaskDefinition as CanonicalTaskDefinition,
    WorkflowDefinition as CanonicalWorkflowDefinition,
)
from pyworkflowkit.contracts.v2_release_candidate import (
    V2_RC_CHANGE_POLICY,
    V2_RC_IDENTITY_TYPES,
    V2_RC_PROTOCOL_METHODS,
    V2_RC_PUBLIC_SURFACES,
    V2_RC_QUALIFICATION_DOMAINS,
    V2_RC_SIBLING_INTEGRATION_CONTRACTS,
    V2_RC_STATE_MEMBERS,
    V2_RC_WIRE_CONTRACTS,
    V2_RELEASE_CANDIDATE_TARGET_RELEASE,
    V2_RELEASE_CANDIDATE_VERSION,
    v2_release_candidate_contract_snapshot,
)
from pyworkflowkit.executors import (
    V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS,
    V2_EXECUTOR_PROTOCOL_METHODS,
)
from pyworkflowkit.integrations.pyingestkit import (
    V2_PYINGESTKIT_INTEGRATION_CONTRACT_VERSION,
)
from pyworkflowkit.integrations.pytransformkit import (
    V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION,
)
from pyworkflowkit.persistence import V2_METADATA_STORE_METHODS
from pyworkflowkit.planning import ExecutionPlan as CanonicalExecutionPlan
from pyworkflowkit.policies import (
    RetryPolicy as CanonicalRetryPolicy,
    TimeoutPolicy as CanonicalTimeoutPolicy,
)
from pyworkflowkit.runtime import (
    TaskAttempt as CanonicalTaskAttempt,
    TaskAttemptId as CanonicalTaskAttemptId,
    TaskRun as CanonicalTaskRun,
    TaskRunId as CanonicalTaskRunId,
    WorkflowResult as CanonicalWorkflowResult,
    WorkflowRun as CanonicalWorkflowRun,
    WorkflowRunId as CanonicalWorkflowRunId,
    WorkflowRuntime as CanonicalWorkflowRuntime,
)
from pyworkflowkit.serialization import V2_BOUNDARY_WIRE_CONTRACTS
from pyworkflowkit.states import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus


def test_lot22_candidate_identity_and_change_policy_are_frozen() -> None:
    assert pyworkflowkit.__version__ == V2_RELEASE_CANDIDATE_VERSION == "2.0.0rc1"
    assert V2_RELEASE_CANDIDATE_TARGET_RELEASE == "2.0.0"
    assert V2_RC_CHANGE_POLICY == "blocker-fixes-only-without-contract-drift"


def test_lot22_package_root_is_exactly_the_v2_target_root() -> None:
    assert tuple(pyworkflowkit.__all__) == V2_ROOT_TARGET_ALLOWLIST
    assert tuple(pyworkflowkit.__all__) == V2_RC_PUBLIC_SURFACES["pyworkflowkit"]

    assert ExecutionPlan is CanonicalExecutionPlan
    assert TaskDefinition is CanonicalTaskDefinition
    assert WorkflowDefinition is CanonicalWorkflowDefinition
    assert RetryPolicy is CanonicalRetryPolicy
    assert TimeoutPolicy is CanonicalTimeoutPolicy
    assert TaskAttempt is CanonicalTaskAttempt
    assert TaskAttemptId is CanonicalTaskAttemptId
    assert TaskRun is CanonicalTaskRun
    assert TaskRunId is CanonicalTaskRunId
    assert WorkflowResult is CanonicalWorkflowResult
    assert WorkflowRun is CanonicalWorkflowRun
    assert WorkflowRunId is CanonicalWorkflowRunId
    assert WorkflowRuntime is CanonicalWorkflowRuntime


def test_lot22_legacy_generic_root_aliases_are_not_preserved() -> None:
    removed = {
        "ArtifactId",
        "ArtifactReference",
        "BackoffStrategy",
        "ExternalRunRef",
        "ExternalRunRefId",
        "FailurePolicy",
        "RunContext",
        "RuntimeSettings",
        "TaskHandle",
        "TaskId",
        "TaskResult",
        "TimeoutMode",
        "WorkflowBuilder",
        "WorkflowId",
        "WorkflowParameter",
        "task",
        "workflow",
    }

    assert removed.isdisjoint(pyworkflowkit.__all__)
    for name in removed:
        assert name not in pyworkflowkit.__dict__


def test_lot22_all_stable_v2_namespace_exports_match_rc_baseline() -> None:
    assert tuple(V2_RC_PUBLIC_SURFACES) == tuple(sorted(V2_RC_PUBLIC_SURFACES))
    assert set(V2_RC_PUBLIC_SURFACES) == set(V2_CANONICAL_PUBLIC_NAMESPACES)

    for module_name, expected in V2_RC_PUBLIC_SURFACES.items():
        module = import_module(module_name)
        assert tuple(module.__all__) == expected, module_name
        assert len(expected) == len(set(expected)), module_name
        for symbol in expected:
            assert hasattr(module, symbol), f"{module_name}.{symbol}"


def test_lot22_runtime_state_members_are_frozen() -> None:
    actual = {
        "WorkflowRunStatus": tuple((item.name, item.value) for item in WorkflowRunStatus),
        "TaskRunStatus": tuple((item.name, item.value) for item in TaskRunStatus),
        "TaskAttemptStatus": tuple((item.name, item.value) for item in TaskAttemptStatus),
    }
    assert actual == dict(V2_RC_STATE_MEMBERS)


def test_lot22_identity_types_are_distinct_and_frozen() -> None:
    assert V2_RC_IDENTITY_TYPES == (
        "WorkflowRunId",
        "TaskRunId",
        "TaskAttemptId",
        "CorrelationId",
    )
    assert len(
        {
            CanonicalWorkflowRunId,
            CanonicalTaskRunId,
            CanonicalTaskAttemptId,
        }
    ) == 3


def test_lot22_executor_and_metadata_protocols_are_frozen() -> None:
    assert V2_EXECUTOR_PROTOCOL_METHODS == V2_RC_PROTOCOL_METHODS["Executor"]
    assert V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS == V2_RC_PROTOCOL_METHODS[
        "CancellableExecutor"
    ]
    assert V2_METADATA_STORE_METHODS == V2_RC_PROTOCOL_METHODS["MetadataStore"]


def test_lot22_wire_contract_identities_and_versions_are_frozen() -> None:
    actual = {
        name: (
            descriptor.contract,
            descriptor.contract_version,
            descriptor.owner,
        )
        for name, descriptor in V2_BOUNDARY_WIRE_CONTRACTS.items()
    }
    assert actual == dict(V2_RC_WIRE_CONTRACTS)


def test_lot22_sibling_contract_ranges_are_explicit() -> None:
    assert V2_RC_SIBLING_INTEGRATION_CONTRACTS == {
        "pyingestkit": V2_PYINGESTKIT_INTEGRATION_CONTRACT_VERSION,
        "pytransformkit": V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION,
    }


def test_lot22_v1_migration_contract_remains_fail_closed() -> None:
    migration = migration_contract_snapshot()

    assert migration["direction"] == "v1_to_v2_only"
    assert migration["generic_aliases_preserved"] is False
    assert migration["ambiguous_external_attempt_ownership_invented"] is False


def test_lot22_qualification_scope_matches_roadmap() -> None:
    assert V2_RC_QUALIFICATION_DOMAINS == (
        "root_api_snapshot",
        "python_matrix",
        "ruff_format_mypy",
        "dag_planning",
        "state_machines",
        "retry_backoff",
        "timeout_cancellation",
        "executor_conformance",
        "metadata_store_conformance",
        "recovery_reconciliation_fault_injection",
        "wire_golden_fixtures",
        "plugin_compatibility",
        "security",
        "sibling_adapter_conformance",
        "optional_extra_isolation",
        "wheel_install",
        "sdist_install",
        "customer_360",
        "migration_fixtures",
        "docs_examples",
        "release_evidence_manifest",
    )


def test_lot22_snapshot_is_deterministic_and_json_serializable() -> None:
    snapshot = v2_release_candidate_contract_snapshot()

    assert snapshot["candidate_version"] == "2.0.0rc1"
    assert snapshot["target_release"] == "2.0.0"
    assert json.loads(json.dumps(snapshot, sort_keys=True)) == snapshot
