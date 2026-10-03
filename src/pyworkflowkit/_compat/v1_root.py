"""Explicit compatibility facade for the historical PyWorkflowKit 1.1 root.

PyWorkflowKit 2.0 intentionally promotes the package root to the canonical V2 API.
Consumers that still need the frozen 1.x root during migration must opt in through this
qualified compatibility module rather than relying on ambiguous package-root aliases.
"""

from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.declarative import TaskHandle, WorkflowBuilder, task, workflow
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import BackoffStrategy, FailurePolicy, TimeoutMode
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
    "TaskHandle",
    "TaskId",
    "TaskResult",
    "TimeoutMode",
    "WorkflowBuilder",
    "WorkflowDefinition",
    "WorkflowId",
    "WorkflowParameter",
    "WorkflowRuntime",
    "task",
    "workflow",
]
