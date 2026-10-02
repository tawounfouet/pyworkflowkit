"""PyWorkflowKit V2 architecture baseline metadata.

LOT-00 records the target semantic package surfaces without changing the stable
1.1 runtime behavior. Later V2 lots progressively replace transitional re-exports
with their canonical implementations.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class StabilityTier(StrEnum):
    STABLE = "stable"
    PROVISIONAL = "provisional"
    INTERNAL = "internal"
    COMPATIBILITY = "compatibility"


V2_ARCHITECTURE_CONTRACT_VERSION = "1"
V2_TARGET_RELEASE = "2.0.0"

V2_CANONICAL_PUBLIC_NAMESPACES: tuple[str, ...] = (
    "pyworkflowkit",
    "pyworkflowkit.authoring",
    "pyworkflowkit.planning",
    "pyworkflowkit.runtime",
    "pyworkflowkit.states",
    "pyworkflowkit.policies",
    "pyworkflowkit.executors",
    "pyworkflowkit.persistence",
    "pyworkflowkit.serialization",
    "pyworkflowkit.lineage",
    "pyworkflowkit.diagnostics",
    "pyworkflowkit.plugins",
    "pyworkflowkit.integrations",
)

V2_NAMESPACE_TIERS: Mapping[str, StabilityTier] = MappingProxyType(
    {
        "pyworkflowkit": StabilityTier.STABLE,
        "pyworkflowkit.authoring": StabilityTier.STABLE,
        "pyworkflowkit.planning": StabilityTier.STABLE,
        "pyworkflowkit.runtime": StabilityTier.STABLE,
        "pyworkflowkit.states": StabilityTier.STABLE,
        "pyworkflowkit.policies": StabilityTier.STABLE,
        "pyworkflowkit.executors": StabilityTier.STABLE,
        "pyworkflowkit.persistence": StabilityTier.STABLE,
        "pyworkflowkit.serialization": StabilityTier.STABLE,
        "pyworkflowkit.lineage": StabilityTier.STABLE,
        "pyworkflowkit.diagnostics": StabilityTier.STABLE,
        "pyworkflowkit.plugins": StabilityTier.STABLE,
        "pyworkflowkit.integrations": StabilityTier.STABLE,
        "pyworkflowkit.control_plane": StabilityTier.PROVISIONAL,
        "pyworkflowkit.ecosystem": StabilityTier.COMPATIBILITY,
        "pyworkflowkit._compat": StabilityTier.COMPATIBILITY,
        "pyworkflowkit._application": StabilityTier.INTERNAL,
        "pyworkflowkit._ports": StabilityTier.INTERNAL,
    }
)

V2_INTERNAL_NAMESPACE_PREFIXES: tuple[str, ...] = (
    "pyworkflowkit._application",
    "pyworkflowkit._ports",
    "pyworkflowkit.persistence._sqlalchemy",
    "pyworkflowkit.planning._graph",
)

V2_LEGACY_FACADES: tuple[str, ...] = ("pyworkflowkit.ecosystem",)

V2_OPTIONAL_SIBLING_IMPORT_OWNERS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "pyingestkit": ("pyworkflowkit.integrations.pyingestkit",),
        "pytransformkit": ("pyworkflowkit.integrations.pytransformkit",),
    }
)

V2_ROOT_TARGET_ALLOWLIST: tuple[str, ...] = (
    "ExecutionPlan",
    "PyWorkflowKitError",
    "RetryPolicy",
    "TaskAttempt",
    "TaskAttemptId",
    "TaskDefinition",
    "TaskRun",
    "TaskRunId",
    "TimeoutPolicy",
    "WorkflowDefinition",
    "WorkflowResult",
    "WorkflowRun",
    "WorkflowRunId",
    "WorkflowRuntime",
    "__version__",
)


def v2_architecture_snapshot() -> dict[str, object]:
    """Return deterministic machine-readable LOT-00 architecture metadata."""

    return {
        "contract_version": V2_ARCHITECTURE_CONTRACT_VERSION,
        "target_release": V2_TARGET_RELEASE,
        "canonical_public_namespaces": list(V2_CANONICAL_PUBLIC_NAMESPACES),
        "namespace_tiers": {
            name: V2_NAMESPACE_TIERS[name].value for name in sorted(V2_NAMESPACE_TIERS)
        },
        "internal_namespace_prefixes": list(V2_INTERNAL_NAMESPACE_PREFIXES),
        "legacy_facades": list(V2_LEGACY_FACADES),
        "optional_sibling_import_owners": {
            package: list(owners)
            for package, owners in sorted(V2_OPTIONAL_SIBLING_IMPORT_OWNERS.items())
        },
        "root_target_allowlist": list(V2_ROOT_TARGET_ALLOWLIST),
    }


__all__ = [
    "StabilityTier",
    "V2_ARCHITECTURE_CONTRACT_VERSION",
    "V2_CANONICAL_PUBLIC_NAMESPACES",
    "V2_INTERNAL_NAMESPACE_PREFIXES",
    "V2_LEGACY_FACADES",
    "V2_NAMESPACE_TIERS",
    "V2_OPTIONAL_SIBLING_IMPORT_OWNERS",
    "V2_ROOT_TARGET_ALLOWLIST",
    "V2_TARGET_RELEASE",
    "v2_architecture_snapshot",
]
