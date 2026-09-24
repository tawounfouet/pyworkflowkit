"""Tests for typed domain identifiers."""

from collections.abc import Callable

import pytest

from pyworkflowkit.domain.ids import (
    ArtifactId,
    ExternalRunRefId,
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
    validate_non_empty_identifier,
)


@pytest.mark.parametrize(
    "factory,value",
    [
        (WorkflowId, "workflow"),
        (TaskId, "task"),
        (WorkflowRunId, "workflow-run"),
        (TaskRunId, "task-run"),
        (TaskAttemptId, "attempt"),
        (RuntimeEventId, "event"),
        (ArtifactId, "artifact"),
        (ExternalRunRefId, "external"),
    ],
)
def test_typed_identifiers_preserve_string_value(
    factory: Callable[[str], str],
    value: str,
) -> None:
    assert factory(value) == value


def test_identifier_validation_preserves_valid_value() -> None:
    assert validate_non_empty_identifier("task-1", field_name="task_id") == "task-1"


@pytest.mark.parametrize("value", ["", " ", "\t", "\n"])
def test_identifier_validation_rejects_blank_values(value: str) -> None:
    with pytest.raises(ValueError, match="task_id must not be empty"):
        validate_non_empty_identifier(value, field_name="task_id")


def test_identifier_validation_rejects_non_string() -> None:
    with pytest.raises(TypeError, match="task_id must be a string"):
        validate_non_empty_identifier(123, field_name="task_id")  # type: ignore[arg-type]
