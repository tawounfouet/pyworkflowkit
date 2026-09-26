"""PyWorkflowKit stable public package surface."""

from importlib.metadata import PackageNotFoundError, version

from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import BackoffStrategy, FailurePolicy
from pyworkflowkit.domain.ids import ArtifactId, ExternalRunRefId, TaskId, WorkflowId
from pyworkflowkit.domain.values import (
    ArtifactReference,
    ExternalRunRef,
    RetryPolicy,
    TaskResult,
    WorkflowParameter,
)
from pyworkflowkit.errors import PyWorkflowKitError
from pyworkflowkit.ports.executor import RunContext

try:
    __version__ = version("pyworkflowkit")
except PackageNotFoundError:  # pragma: no cover - source-tree fallback
    __version__ = "0.0.0+unknown"

__all__ = [
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
    "TaskId",
    "TaskResult",
    "WorkflowDefinition",
    "WorkflowId",
    "WorkflowParameter",
    "WorkflowRuntime",
    "__version__",
]
