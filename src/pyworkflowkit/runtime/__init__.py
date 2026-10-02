"""V2 semantic runtime namespace.

LOT-01 introduces canonical execution identities and portable boundary values.
The durable WorkflowRun/TaskRun/TaskAttempt entities remain the qualified 1.1
implementation until LOT-04 migrates their state contracts.
"""

from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.identity import (
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)
from pyworkflowkit.runtime.references import ExternalRunRef, WorkflowExecutionReference

__all__ = [
    "CorrelationContext",
    "CorrelationId",
    "ExternalRunRef",
    "RuntimeEvent",
    "RuntimeSettings",
    "TaskAttempt",
    "TaskAttemptId",
    "TaskRun",
    "TaskRunId",
    "WorkflowExecutionReference",
    "WorkflowRun",
    "WorkflowRunId",
    "WorkflowRuntime",
]
