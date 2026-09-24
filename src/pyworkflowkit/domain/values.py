"""Immutable value objects used by workflow definitions and task results."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType

from pyworkflowkit.domain.enums import BackoffStrategy
from pyworkflowkit.domain.ids import ArtifactId, ExternalRunRefId, validate_non_empty_identifier


def _require_non_empty_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")
    return value


def _freeze_metadata(metadata: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(metadata))


def _validate_non_negative_number(value: float, *, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a finite number.")
    if not isfinite(value):
        raise ValueError(f"{field_name} must be finite.")
    if value < 0:
        raise ValueError(f"{field_name} must be greater than or equal to 0.")


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Retry semantics for a task definition.

    max_attempts includes the initial attempt. A value of 1 therefore means
    that no retry is permitted.
    """

    max_attempts: int = 1
    backoff_strategy: BackoffStrategy = BackoffStrategy.NONE
    delay_seconds: float = 0.0
    max_delay_seconds: float | None = None
    retryable_error_categories: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if isinstance(self.max_attempts, bool) or not isinstance(self.max_attempts, int):
            raise TypeError("max_attempts must be an integer.")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be greater than or equal to 1.")

        _validate_non_negative_number(self.delay_seconds, field_name="delay_seconds")
        if self.max_delay_seconds is not None:
            _validate_non_negative_number(
                self.max_delay_seconds,
                field_name="max_delay_seconds",
            )

        categories = frozenset(self.retryable_error_categories)
        for category in categories:
            _require_non_empty_text(category, field_name="retryable_error_category")
        object.__setattr__(self, "retryable_error_categories", categories)


@dataclass(frozen=True, slots=True)
class ArtifactReference:
    """Lightweight pointer to an artifact produced by a task."""

    artifact_id: ArtifactId
    name: str
    uri: str
    media_type: str | None = None
    checksum: str | None = None
    size_bytes: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_identifier(str(self.artifact_id), field_name="artifact_id")
        _require_non_empty_text(self.name, field_name="name")
        _require_non_empty_text(self.uri, field_name="uri")

        if self.media_type is not None:
            _require_non_empty_text(self.media_type, field_name="media_type")
        if self.checksum is not None:
            _require_non_empty_text(self.checksum, field_name="checksum")

        if self.size_bytes is not None:
            if isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int):
                raise TypeError("size_bytes must be an integer.")
            if self.size_bytes < 0:
                raise ValueError("size_bytes must be greater than or equal to 0.")

        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class ExternalRunRef:
    """Correlation reference to an execution owned by an external runtime."""

    external_ref_id: ExternalRunRefId
    provider: str
    external_run_id: str
    uri: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_identifier(
            str(self.external_ref_id),
            field_name="external_ref_id",
        )
        _require_non_empty_text(self.provider, field_name="provider")
        _require_non_empty_text(self.external_run_id, field_name="external_run_id")
        if self.uri is not None:
            _require_non_empty_text(self.uri, field_name="uri")
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True, slots=True)
class WorkflowParameter:
    """Minimal declaration of an input parameter accepted by a workflow."""

    name: str
    required: bool = True
    default: object | None = None
    sensitive: bool = False

    def __post_init__(self) -> None:
        _require_non_empty_text(self.name, field_name="name")


@dataclass(frozen=True, slots=True)
class TaskResult:
    """Normalized in-process result returned by a task handler."""

    output: object | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    artifacts: tuple[ArtifactReference, ...] = ()
    external_refs: tuple[ExternalRunRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "external_refs", tuple(self.external_refs))


__all__ = [
    "ArtifactReference",
    "ExternalRunRef",
    "RetryPolicy",
    "TaskResult",
    "WorkflowParameter",
]
