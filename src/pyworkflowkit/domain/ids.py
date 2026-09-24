"""Typed identity aliases used by the PyWorkflowKit domain."""

from typing import NewType

WorkflowId = NewType("WorkflowId", str)
TaskId = NewType("TaskId", str)
WorkflowRunId = NewType("WorkflowRunId", str)
TaskRunId = NewType("TaskRunId", str)
TaskAttemptId = NewType("TaskAttemptId", str)
RuntimeEventId = NewType("RuntimeEventId", str)
ArtifactId = NewType("ArtifactId", str)
ExternalRunRefId = NewType("ExternalRunRefId", str)


def validate_non_empty_identifier(value: str, *, field_name: str) -> str:
    """Validate a text identifier without silently normalizing it."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")
    return value


__all__ = [
    "ArtifactId",
    "ExternalRunRefId",
    "RuntimeEventId",
    "TaskAttemptId",
    "TaskId",
    "TaskRunId",
    "WorkflowId",
    "WorkflowRunId",
]
