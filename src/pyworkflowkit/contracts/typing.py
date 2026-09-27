"""Machine-readable static typing contract for the PyWorkflowKit 1.0 line."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from pyworkflowkit.public_api import PUBLIC_API_SURFACES

TYPING_CONTRACT_VERSION = "1"
TYPING_TARGET_RELEASE = "1.0.0"
TYPING_MARKER = "py.typed"
STATIC_TYPE_CHECKER = "mypy"
STATIC_TYPE_CHECKER_MODE = "strict"

TYPING_FACADES: tuple[str, ...] = tuple(sorted(PUBLIC_API_SURFACES))

ECOSYSTEM_PROTOCOL_SUPPORT_EXPORTS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "executor": (
            "CancellationCapability",
            "Executor",
            "ExecutorCapabilities",
            "RunContext",
            "TaskDefinition",
            "TaskHandler",
            "TaskResult",
            "TimeoutCapability",
        ),
        "metadata": (
            "ArtifactReference",
            "ExternalRunRef",
            "MetadataStore",
            "RuntimeEvent",
            "TaskAttempt",
            "TaskRun",
            "TaskRunId",
            "UnitOfWork",
            "WorkflowRun",
            "WorkflowRunId",
        ),
        "observability": (
            "RuntimeEvent",
            "RuntimeEventSink",
        ),
    }
)


def typing_contract_snapshot() -> dict[str, object]:
    """Return deterministic JSON-portable metadata for RQ-03."""

    return {
        "contract_version": TYPING_CONTRACT_VERSION,
        "target_release": TYPING_TARGET_RELEASE,
        "marker": TYPING_MARKER,
        "checker": {
            "name": STATIC_TYPE_CHECKER,
            "mode": STATIC_TYPE_CHECKER_MODE,
        },
        "facades": list(TYPING_FACADES),
        "ecosystem_protocol_support_exports": {
            protocol: list(exports)
            for protocol, exports in sorted(ECOSYSTEM_PROTOCOL_SUPPORT_EXPORTS.items())
        },
    }


__all__ = [
    "ECOSYSTEM_PROTOCOL_SUPPORT_EXPORTS",
    "STATIC_TYPE_CHECKER",
    "STATIC_TYPE_CHECKER_MODE",
    "TYPING_CONTRACT_VERSION",
    "TYPING_FACADES",
    "TYPING_MARKER",
    "TYPING_TARGET_RELEASE",
    "typing_contract_snapshot",
]
