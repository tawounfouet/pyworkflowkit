"""PyWorkflowKit 2.0 release-candidate freeze and evidence manifest."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from pyworkflowkit._architecture import v2_architecture_snapshot
from pyworkflowkit._compat.v1_to_v2 import migration_contract_snapshot
from pyworkflowkit.authoring.contracts import v2_authoring_contract_snapshot
from pyworkflowkit.executors.contracts import (
    V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS,
    V2_EXECUTOR_PROTOCOL_METHODS,
    v2_executor_contract_snapshot,
)
from pyworkflowkit.integrations.pyingestkit import v2_pyingestkit_integration_snapshot
from pyworkflowkit.integrations.pytransformkit import v2_pytransformkit_integration_snapshot
from pyworkflowkit.persistence.contracts import (
    V2_METADATA_STORE_METHODS,
    v2_metadata_store_contract_snapshot,
)
from pyworkflowkit.planning.contracts import v2_planning_contract_snapshot
from pyworkflowkit.plugins.v2 import v2_plugin_contract_snapshot
from pyworkflowkit.policies.retry import v2_retry_contract_snapshot
from pyworkflowkit.policies.timeout import v2_timeout_contract_snapshot
from pyworkflowkit.public_api import v2_root_public_api_snapshot
from pyworkflowkit.runtime.contracts import v2_runtime_mvp_contract_snapshot
from pyworkflowkit.serialization import v2_boundary_wire_contract_snapshot
from pyworkflowkit.states.contracts import v2_state_contract_snapshot

V2_RELEASE_CANDIDATE_CONTRACT_VERSION = "1"
V2_RELEASE_CANDIDATE_VERSION = "2.0.0rc1"
V2_RELEASE_CANDIDATE_TARGET_RELEASE = "2.0.0"

V2_SUPPORTED_PYTHON_VERSIONS: tuple[str, ...] = ("3.11", "3.12", "3.13")

V2_STABLE_IDENTITIES: tuple[str, ...] = (
    "CorrelationId",
    "WorkflowRunId",
    "TaskRunId",
    "TaskAttemptId",
)

V2_STABLE_PROTOCOLS: dict[str, tuple[str, ...]] = {
    "WorkloadDescriptor": ("workload_kind", "portability", "fingerprint_payload"),
    "Executor": V2_EXECUTOR_PROTOCOL_METHODS,
    "CancellableExecutor": V2_CANCELLABLE_EXECUTOR_PROTOCOL_METHODS,
    "MetadataStore": V2_METADATA_STORE_METHODS,
    "ExternalRunVerifier": ("provider", "verify"),
    "V2RuntimeEventSink": ("name", "emit"),
}

V2_RC_REQUIRED_QUALIFICATION_FAMILIES: tuple[str, ...] = (
    "root-api",
    "python-matrix",
    "quality",
    "dag-planning",
    "state-machines",
    "retry-backoff",
    "timeout-cancellation",
    "executor-conformance",
    "metadata-store-conformance",
    "recovery-reconciliation",
    "wire-golden-fixtures",
    "plugin-compatibility",
    "security",
    "sibling-adapter-conformance",
    "optional-extra-isolation",
    "wheel-install",
    "sdist-install",
    "customer360",
    "migration-fixtures",
    "docs-examples",
    "release-evidence-manifest",
)

V2_RC_CHANGE_POLICY = "blocker-fixes-only-without-rc-reset"


def _package_version() -> str:
    try:
        return version("pyworkflowkit")
    except PackageNotFoundError:  # pragma: no cover - source-tree fallback
        return "0.0.0+unknown"


def v2_release_candidate_evidence_manifest() -> dict[str, object]:
    """Return the deterministic LOT-22 qualification and compatibility manifest."""

    return {
        "contract_version": V2_RELEASE_CANDIDATE_CONTRACT_VERSION,
        "candidate_version": V2_RELEASE_CANDIDATE_VERSION,
        "target_release": V2_RELEASE_CANDIDATE_TARGET_RELEASE,
        "package_version": _package_version(),
        "supported_python_versions": list(V2_SUPPORTED_PYTHON_VERSIONS),
        "change_policy": V2_RC_CHANGE_POLICY,
        "architecture_redesign_permitted": False,
        "stable_identities": list(V2_STABLE_IDENTITIES),
        "stable_protocols": {
            key: list(value) for key, value in sorted(V2_STABLE_PROTOCOLS.items())
        },
        "required_qualification_families": list(
            V2_RC_REQUIRED_QUALIFICATION_FAMILIES
        ),
        "contracts": {
            "architecture": v2_architecture_snapshot(),
            "root_api": v2_root_public_api_snapshot(),
            "authoring": v2_authoring_contract_snapshot(),
            "planning": v2_planning_contract_snapshot(),
            "states": v2_state_contract_snapshot(),
            "runtime": v2_runtime_mvp_contract_snapshot(),
            "retry": v2_retry_contract_snapshot(),
            "timeout": v2_timeout_contract_snapshot(),
            "executor": v2_executor_contract_snapshot(),
            "metadata_store": v2_metadata_store_contract_snapshot(),
            "wire": v2_boundary_wire_contract_snapshot(),
            "plugins": v2_plugin_contract_snapshot(),
            "pyingestkit": v2_pyingestkit_integration_snapshot(),
            "pytransformkit": v2_pytransformkit_integration_snapshot(),
            "migration": migration_contract_snapshot(),
        },
    }


__all__ = [
    "V2_RC_CHANGE_POLICY",
    "V2_RC_REQUIRED_QUALIFICATION_FAMILIES",
    "V2_RELEASE_CANDIDATE_CONTRACT_VERSION",
    "V2_RELEASE_CANDIDATE_TARGET_RELEASE",
    "V2_RELEASE_CANDIDATE_VERSION",
    "V2_STABLE_IDENTITIES",
    "V2_STABLE_PROTOCOLS",
    "V2_SUPPORTED_PYTHON_VERSIONS",
    "v2_release_candidate_evidence_manifest",
]
