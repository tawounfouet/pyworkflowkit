"""Canonical PyWorkflowKit V2 execution identifiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Identifier:
    """Immutable opaque identifier value.

    V2 identifiers are distinct runtime types. Their textual representation is
    intentionally opaque: consumers must not infer storage or routing semantics
    from the identifier value.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("identifier value must be a string")
        if not self.value.strip():
            raise ValueError("identifier value must not be empty")

    @classmethod
    def new(cls) -> Self:
        """Create a new opaque identifier of the concrete type."""

        return cls(str(uuid4()))

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a portable textual identifier without changing its value."""

        return cls(value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class WorkflowRunId(Identifier):
    """Identity of one WorkflowDefinition execution."""


@dataclass(frozen=True, slots=True)
class TaskRunId(Identifier):
    """Identity of one logical task execution within a WorkflowRun."""


@dataclass(frozen=True, slots=True)
class TaskAttemptId(Identifier):
    """Identity of one concrete TaskRun attempt."""


@dataclass(frozen=True, slots=True)
class CorrelationId(Identifier):
    """Identity grouping related work without replacing native execution IDs."""


__all__ = [
    "CorrelationId",
    "Identifier",
    "TaskAttemptId",
    "TaskRunId",
    "WorkflowRunId",
]
