"""PyWorkflowKit 2.x canonical public package surface."""

from importlib.metadata import PackageNotFoundError, version

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.errors import PyWorkflowKitError
from pyworkflowkit.planning import ExecutionPlan
from pyworkflowkit.policies import RetryPolicy, TimeoutPolicy
from pyworkflowkit.runtime import (
    TaskAttempt,
    TaskAttemptId,
    TaskRun,
    TaskRunId,
    WorkflowResult,
    WorkflowRun,
    WorkflowRunId,
    WorkflowRuntime,
)

try:
    __version__ = version("pyworkflowkit")
except PackageNotFoundError:  # pragma: no cover - source-tree fallback
    __version__ = "0.0.0+unknown"

__all__ = [
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
]
