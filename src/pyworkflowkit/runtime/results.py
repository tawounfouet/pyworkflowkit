"""Immutable caller-facing V2 workflow result projections."""

from __future__ import annotations

from dataclasses import dataclass

from pyworkflowkit.diagnostics import Diagnostic, FailureEvidence
from pyworkflowkit.persistence import ManifestReference
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.identity import TaskAttemptId, TaskRunId, WorkflowRunId
from pyworkflowkit.states import TaskRunStatus, WorkflowRunStatus
from pyworkflowkit.states.enums import WORKFLOW_TERMINAL_STATUSES


@dataclass(frozen=True, slots=True)
class TaskOutcome:
    """Read-only summary of one logical TaskRun."""

    task_key: str
    task_run_id: TaskRunId
    status: TaskRunStatus
    attempt_ids: tuple[TaskAttemptId, ...] = ()
    output: object = None
    failure: FailureEvidence | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.task_key, str) or not self.task_key.strip():
            raise ValueError("task_key must not be empty")
        if not isinstance(self.task_run_id, TaskRunId):
            raise TypeError("task_run_id must be a TaskRunId")
        if not isinstance(self.status, TaskRunStatus):
            raise TypeError("status must be a TaskRunStatus")
        attempts = tuple(self.attempt_ids)
        if not all(isinstance(item, TaskAttemptId) for item in attempts):
            raise TypeError("attempt_ids must contain only TaskAttemptId values")
        diagnostics = tuple(self.diagnostics)
        if not all(isinstance(item, Diagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain only Diagnostic values")
        object.__setattr__(self, "attempt_ids", attempts)
        object.__setattr__(self, "diagnostics", diagnostics)


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Small immutable result returned by WorkflowRuntime.run()."""

    run_id: WorkflowRunId
    status: WorkflowRunStatus
    task_outcomes: tuple[TaskOutcome, ...]
    diagnostics: tuple[Diagnostic, ...]
    correlation: CorrelationContext
    failure: FailureEvidence | None = None
    manifest_reference: ManifestReference | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, WorkflowRunId):
            raise TypeError("run_id must be a WorkflowRunId")
        if not isinstance(self.status, WorkflowRunStatus):
            raise TypeError("status must be a WorkflowRunStatus")
        if self.status not in WORKFLOW_TERMINAL_STATUSES:
            raise ValueError("WorkflowResult requires a terminal WorkflowRun status")
        outcomes = tuple(self.task_outcomes)
        keys = tuple(item.task_key for item in outcomes)
        if len(keys) != len(set(keys)):
            raise ValueError("task_outcomes must contain unique task keys")
        diagnostics = tuple(self.diagnostics)
        if not all(isinstance(item, Diagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain only Diagnostic values")
        if not isinstance(self.correlation, CorrelationContext):
            raise TypeError("correlation must be a CorrelationContext")
        object.__setattr__(self, "task_outcomes", outcomes)
        object.__setattr__(self, "diagnostics", diagnostics)

    def task(self, key: str) -> TaskOutcome:
        for outcome in self.task_outcomes:
            if outcome.task_key == key:
                return outcome
        raise KeyError(key)


__all__ = ["TaskOutcome", "WorkflowResult"]
