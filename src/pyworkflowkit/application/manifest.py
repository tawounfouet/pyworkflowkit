"""Build and serialize deterministic execution manifests."""

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import Enum
from math import isfinite
from typing import cast

from pyworkflowkit.domain.definitions import WorkflowDefinition
from pyworkflowkit.domain.enums import (
    ATTEMPT_TERMINAL_STATUSES,
    TASK_TERMINAL_STATUSES,
    WORKFLOW_TERMINAL_STATUSES,
    RuntimeEventType,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import WorkflowRunId
from pyworkflowkit.domain.manifest import (
    JsonValue,
    ManifestArtifact,
    ManifestAttempt,
    ManifestEvent,
    ManifestExternalRunRef,
    ManifestTaskRun,
    RunManifest,
)
from pyworkflowkit.domain.runtime import RuntimeEvent, TaskAttempt, TaskRun, WorkflowRun
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef
from pyworkflowkit.errors import (
    ManifestInvariantError,
    ManifestNotReadyError,
    ManifestSerializationError,
)
from pyworkflowkit.ports.metadata_store import MetadataStore

MANIFEST_SCHEMA_VERSION = "1"
REDACTED_VALUE = "<redacted>"


class RunManifestBuilder:
    """Reconstruct portable final evidence from a MetadataStore."""

    def __init__(self, *, metadata_store: MetadataStore) -> None:
        self._metadata_store = metadata_store

    def build(
        self,
        *,
        workflow: WorkflowDefinition,
        run_id: WorkflowRunId,
    ) -> RunManifest:
        run = self._metadata_store.get_workflow_run(run_id)
        self._validate_workflow_identity(workflow=workflow, run=run)
        self._validate_terminal_run(run)

        task_runs = tuple(
            sorted(
                self._metadata_store.list_task_runs(run_id),
                key=lambda task_run: str(task_run.task_id),
            )
        )
        self._validate_task_runs(task_runs)

        events = tuple(
            sorted(
                self._metadata_store.list_events(run_id),
                key=lambda event: (
                    event.event_sequence if event.event_sequence is not None else 2**63 - 1,
                    str(event.event_id),
                ),
            )
        )
        self._validate_events(run=run, events=events)

        sensitive_parameters = frozenset(
            parameter.name for parameter in workflow.parameters if parameter.sensitive
        )

        return RunManifest(
            schema_version=MANIFEST_SCHEMA_VERSION,
            run_id=str(run.run_id),
            workflow_id=str(run.workflow_id),
            workflow_version=run.workflow_version,
            status=run.status.value,
            parameters={
                name: (
                    REDACTED_VALUE
                    if name in sensitive_parameters
                    else _to_json_value(value, path=f"parameters.{name}")
                )
                for name, value in sorted(run.parameters.items())
            },
            created_at=_iso_datetime(run.created_at),
            started_at=_iso_datetime(run.started_at),
            finished_at=_iso_datetime(run.finished_at),
            tasks=tuple(self._task_manifest(task_run) for task_run in task_runs),
            events=tuple(self._event_manifest(event) for event in events),
        )

    def _task_manifest(self, task_run: TaskRun) -> ManifestTaskRun:
        attempts = tuple(
            sorted(
                self._metadata_store.list_task_attempts(task_run.task_run_id),
                key=lambda attempt: attempt.attempt_number,
            )
        )
        self._validate_attempts(task_run=task_run, attempts=attempts)

        artifacts = tuple(
            sorted(
                self._metadata_store.list_artifacts(task_run.task_run_id),
                key=lambda artifact: str(artifact.artifact_id),
            )
        )
        external_refs = tuple(
            sorted(
                self._metadata_store.list_external_run_refs(task_run.task_run_id),
                key=lambda external_ref: str(external_ref.external_ref_id),
            )
        )

        return ManifestTaskRun(
            task_run_id=str(task_run.task_run_id),
            task_id=str(task_run.task_id),
            status=task_run.status.value,
            skip_reason=(task_run.skip_reason.value if task_run.skip_reason is not None else None),
            created_at=_iso_datetime(task_run.created_at),
            started_at=_iso_datetime(task_run.started_at),
            finished_at=_iso_datetime(task_run.finished_at),
            attempts=tuple(_attempt_manifest(attempt) for attempt in attempts),
            artifacts=tuple(_artifact_manifest(artifact) for artifact in artifacts),
            external_refs=tuple(
                _external_ref_manifest(external_ref) for external_ref in external_refs
            ),
        )

    @staticmethod
    def _validate_workflow_identity(
        *,
        workflow: WorkflowDefinition,
        run: WorkflowRun,
    ) -> None:
        if workflow.workflow_id != run.workflow_id:
            raise ManifestInvariantError(
                reason=(
                    f"workflow id mismatch: definition={workflow.workflow_id}, "
                    f"run={run.workflow_id}"
                )
            )
        if workflow.version != run.workflow_version:
            raise ManifestInvariantError(
                reason=(
                    f"workflow version mismatch: definition={workflow.version}, "
                    f"run={run.workflow_version}"
                )
            )

    @staticmethod
    def _validate_terminal_run(run: WorkflowRun) -> None:
        if run.status not in WORKFLOW_TERMINAL_STATUSES:
            raise ManifestNotReadyError(
                run_id=str(run.run_id),
                status=run.status.value,
            )

    @staticmethod
    def _validate_task_runs(task_runs: Sequence[TaskRun]) -> None:
        for task_run in task_runs:
            if task_run.status not in TASK_TERMINAL_STATUSES:
                raise ManifestInvariantError(
                    reason=(f"task '{task_run.task_id}' is not terminal: {task_run.status.value}")
                )

    @staticmethod
    def _validate_attempts(
        *,
        task_run: TaskRun,
        attempts: Sequence[TaskAttempt],
    ) -> None:
        expected_number = 1
        for attempt in attempts:
            if attempt.attempt_number != expected_number:
                raise ManifestInvariantError(
                    reason=(
                        f"task '{task_run.task_id}' attempt sequence is not contiguous "
                        f"at {attempt.attempt_number}"
                    )
                )
            if attempt.status not in ATTEMPT_TERMINAL_STATUSES:
                raise ManifestInvariantError(
                    reason=(
                        f"task '{task_run.task_id}' has non-terminal attempt "
                        f"{attempt.attempt_number}: {attempt.status.value}"
                    )
                )
            expected_number += 1

    @staticmethod
    def _validate_events(
        *,
        run: WorkflowRun,
        events: Sequence[RuntimeEvent],
    ) -> None:
        if not events:
            raise ManifestInvariantError(reason="terminal run has no runtime events")

        previous_sequence = 0
        for event in events:
            if event.event_sequence is None or event.event_sequence <= previous_sequence:
                raise ManifestInvariantError(
                    reason=(
                        "runtime event sequence is not strictly increasing: "
                        f"previous {previous_sequence}, got {event.event_sequence}"
                    )
                )
            previous_sequence = event.event_sequence

        expected_terminal_event = {
            WorkflowRunStatus.SUCCEEDED: RuntimeEventType.WORKFLOW_SUCCEEDED,
            WorkflowRunStatus.FAILED: RuntimeEventType.WORKFLOW_FAILED,
            WorkflowRunStatus.CANCELLED: RuntimeEventType.WORKFLOW_CANCELLED,
        }[run.status]
        if events[-1].event_type is not expected_terminal_event:
            raise ManifestInvariantError(
                reason=(
                    f"terminal event mismatch: expected {expected_terminal_event.value}, "
                    f"got {events[-1].event_type.value}"
                )
            )

    @staticmethod
    def _event_manifest(event: RuntimeEvent) -> ManifestEvent:
        if event.event_sequence is None:
            raise ManifestInvariantError(reason=f"event '{event.event_id}' has no event_sequence")
        return ManifestEvent(
            event_id=str(event.event_id),
            event_sequence=event.event_sequence,
            event_type=event.event_type.value,
            occurred_at=_iso_datetime_required(event.occurred_at),
            task_run_id=(str(event.task_run_id) if event.task_run_id is not None else None),
            task_id=str(event.task_id) if event.task_id is not None else None,
            attempt_number=event.attempt_number,
            payload={
                key: _to_json_value(value, path=f"event.{event.event_id}.{key}")
                for key, value in sorted(event.payload.items())
            },
        )


class RunManifestSerializer:
    """Canonical JSON serializer for RunManifest."""

    def to_dict(self, manifest: RunManifest) -> dict[str, object]:
        return {
            "schema_version": manifest.schema_version,
            "run_id": manifest.run_id,
            "workflow_id": manifest.workflow_id,
            "workflow_version": manifest.workflow_version,
            "status": manifest.status,
            "parameters": _plain_mapping(manifest.parameters),
            "created_at": manifest.created_at,
            "started_at": manifest.started_at,
            "finished_at": manifest.finished_at,
            "tasks": [self._task_to_dict(task) for task in manifest.tasks],
            "events": [self._event_to_dict(event) for event in manifest.events],
        }

    def to_json(self, manifest: RunManifest) -> str:
        return json.dumps(
            self.to_dict(manifest),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    def _task_to_dict(self, task: ManifestTaskRun) -> dict[str, object]:
        return {
            "task_run_id": task.task_run_id,
            "task_id": task.task_id,
            "status": task.status,
            "skip_reason": task.skip_reason,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "attempts": [
                {
                    "attempt_id": attempt.attempt_id,
                    "attempt_number": attempt.attempt_number,
                    "status": attempt.status,
                    "started_at": attempt.started_at,
                    "finished_at": attempt.finished_at,
                    "error_type": attempt.error_type,
                    "error_category": attempt.error_category,
                }
                for attempt in task.attempts
            ],
            "artifacts": [
                {
                    "artifact_id": artifact.artifact_id,
                    "name": artifact.name,
                    "uri": artifact.uri,
                    "media_type": artifact.media_type,
                    "checksum": artifact.checksum,
                    "size_bytes": artifact.size_bytes,
                    "metadata": _plain_mapping(artifact.metadata),
                }
                for artifact in task.artifacts
            ],
            "external_refs": [
                {
                    "external_ref_id": external_ref.external_ref_id,
                    "provider": external_ref.provider,
                    "external_run_id": external_ref.external_run_id,
                    "uri": external_ref.uri,
                    "metadata": _plain_mapping(external_ref.metadata),
                }
                for external_ref in task.external_refs
            ],
        }

    @staticmethod
    def _event_to_dict(event: ManifestEvent) -> dict[str, object]:
        return {
            "event_id": event.event_id,
            "event_sequence": event.event_sequence,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at,
            "task_run_id": event.task_run_id,
            "task_id": event.task_id,
            "attempt_number": event.attempt_number,
            "payload": _plain_mapping(event.payload),
        }


def _attempt_manifest(attempt: TaskAttempt) -> ManifestAttempt:
    return ManifestAttempt(
        attempt_id=str(attempt.attempt_id),
        attempt_number=attempt.attempt_number,
        status=attempt.status.value,
        started_at=_iso_datetime(attempt.started_at),
        finished_at=_iso_datetime(attempt.finished_at),
        error_type=attempt.error_type,
        error_category=attempt.error_category,
    )


def _artifact_manifest(artifact: ArtifactReference) -> ManifestArtifact:
    return ManifestArtifact(
        artifact_id=str(artifact.artifact_id),
        name=artifact.name,
        uri=artifact.uri,
        media_type=artifact.media_type,
        checksum=artifact.checksum,
        size_bytes=artifact.size_bytes,
        metadata={
            key: _to_json_value(value, path=f"artifact.{artifact.artifact_id}.{key}")
            for key, value in sorted(artifact.metadata.items())
        },
    )


def _external_ref_manifest(external_ref: ExternalRunRef) -> ManifestExternalRunRef:
    return ManifestExternalRunRef(
        external_ref_id=str(external_ref.external_ref_id),
        provider=external_ref.provider,
        external_run_id=external_ref.external_run_id,
        uri=external_ref.uri,
        metadata={
            key: _to_json_value(
                value,
                path=f"external_ref.{external_ref.external_ref_id}.{key}",
            )
            for key, value in sorted(external_ref.metadata.items())
        },
    )


def _iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _iso_datetime_required(value)


def _iso_datetime_required(value: datetime) -> str:
    rendered = value.isoformat()
    return rendered.replace("+00:00", "Z")


def _to_json_value(value: object, *, path: str) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return cast(JsonValue, value)
    if isinstance(value, float):
        if not isfinite(value):
            raise ManifestSerializationError(
                path=path,
                value_type=type(value).__name__,
            )
        return value
    if isinstance(value, Enum):
        return _to_json_value(value.value, path=path)
    if isinstance(value, Mapping):
        normalized: dict[str, JsonValue] = {}
        for key, nested_value in sorted(value.items(), key=lambda item: str(item[0])):
            if not isinstance(key, str):
                raise ManifestSerializationError(
                    path=path,
                    value_type=f"mapping-key:{type(key).__name__}",
                )
            normalized[key] = _to_json_value(
                nested_value,
                path=f"{path}.{key}",
            )
        return normalized
    if isinstance(value, (list, tuple)):
        return tuple(
            _to_json_value(item, path=f"{path}[{index}]") for index, item in enumerate(value)
        )
    raise ManifestSerializationError(
        path=path,
        value_type=type(value).__name__,
    )


def _plain_mapping(values: Mapping[str, JsonValue]) -> dict[str, object]:
    return {key: _plain_json_value(value) for key, value in values.items()}


def _plain_json_value(value: JsonValue) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_json_value(nested_value) for key, nested_value in value.items()}
    if isinstance(value, tuple):
        return [_plain_json_value(item) for item in value]
    return value


__all__ = [
    "MANIFEST_SCHEMA_VERSION",
    "REDACTED_VALUE",
    "RunManifestBuilder",
    "RunManifestSerializer",
]
