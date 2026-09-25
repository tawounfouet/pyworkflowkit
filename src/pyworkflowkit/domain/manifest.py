"""Immutable execution-manifest values."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | tuple["JsonValue", ...] | Mapping[str, "JsonValue"]


def _freeze_json_mapping(
    values: Mapping[str, JsonValue],
) -> Mapping[str, JsonValue]:
    return MappingProxyType(dict(values))


@dataclass(frozen=True, slots=True)
class ManifestAttempt:
    attempt_id: str
    attempt_number: int
    status: str
    started_at: str | None
    finished_at: str | None
    error_type: str | None = None
    error_category: str | None = None


@dataclass(frozen=True, slots=True)
class ManifestArtifact:
    artifact_id: str
    name: str
    uri: str
    media_type: str | None = None
    checksum: str | None = None
    size_bytes: int | None = None
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_json_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class ManifestExternalRunRef:
    external_ref_id: str
    provider: str
    external_run_id: str
    uri: str | None = None
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_json_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class ManifestTaskRun:
    task_run_id: str
    task_id: str
    status: str
    skip_reason: str | None
    created_at: str | None
    started_at: str | None
    finished_at: str | None
    attempts: tuple[ManifestAttempt, ...] = ()
    artifacts: tuple[ManifestArtifact, ...] = ()
    external_refs: tuple[ManifestExternalRunRef, ...] = ()


@dataclass(frozen=True, slots=True)
class ManifestEvent:
    event_id: str
    event_sequence: int
    event_type: str
    occurred_at: str
    task_run_id: str | None
    task_id: str | None
    attempt_number: int | None
    payload: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _freeze_json_mapping(self.payload))


@dataclass(frozen=True, slots=True)
class RunManifest:
    """Portable immutable evidence for one terminal WorkflowRun."""

    schema_version: str
    run_id: str
    workflow_id: str
    workflow_version: str
    status: str
    parameters: Mapping[str, JsonValue]
    created_at: str | None
    started_at: str | None
    finished_at: str | None
    tasks: tuple[ManifestTaskRun, ...]
    events: tuple[ManifestEvent, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", _freeze_json_mapping(self.parameters))


__all__ = [
    "JsonScalar",
    "JsonValue",
    "ManifestArtifact",
    "ManifestAttempt",
    "ManifestEvent",
    "ManifestExternalRunRef",
    "ManifestTaskRun",
    "RunManifest",
]
