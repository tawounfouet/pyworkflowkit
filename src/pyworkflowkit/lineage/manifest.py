"""Build canonical V2 run manifests from durable MetadataStore evidence."""

from __future__ import annotations

from pyworkflowkit.errors import MetadataNotFoundError, RuntimeInvariantError
from pyworkflowkit.lineage.model import (
    ManifestAttempt,
    ManifestTaskRun,
    RunManifest,
)
from pyworkflowkit.persistence import MetadataStore
from pyworkflowkit.runtime.identity import WorkflowRunId
from pyworkflowkit.states.enums import WORKFLOW_TERMINAL_STATUSES

MANIFEST_SCHEMA_VERSION = "2"


class RunManifestBuilder:
    """Reconstruct deterministic durable runtime evidence without executing workloads."""

    def __init__(self, *, metadata: MetadataStore) -> None:
        if not isinstance(metadata, MetadataStore):
            raise TypeError("metadata must satisfy the V2 MetadataStore Protocol")
        self._metadata = metadata

    def build(
        self,
        workflow_run_id: WorkflowRunId,
        *,
        require_terminal: bool = False,
    ) -> RunManifest:
        run = self._metadata.get_workflow_run(workflow_run_id)
        if require_terminal and run.status not in WORKFLOW_TERMINAL_STATUSES:
            raise RuntimeInvariantError(
                reason=(
                    "terminal manifest requested for non-terminal WorkflowRun "
                    f"{workflow_run_id}: {run.status.value}"
                )
            )

        tasks: list[ManifestTaskRun] = []
        for task_run in self._metadata.list_task_runs(workflow_run_id):
            attempts = self._metadata.list_task_attempts(task_run.task_run_id)
            external_runs = tuple(
                external_ref
                for attempt in attempts
                for external_ref in self._metadata.list_external_run_refs(attempt.attempt_id)
            )
            try:
                checkpoint = self._metadata.get_task_output_checkpoint(task_run.task_run_id)
            except MetadataNotFoundError:
                checkpoint = None

            tasks.append(
                ManifestTaskRun(
                    task_run_id=task_run.task_run_id,
                    task_key=task_run.task_key,
                    status=task_run.status,
                    attempts=tuple(
                        ManifestAttempt(
                            attempt_id=attempt.attempt_id,
                            attempt_number=attempt.attempt_number,
                            status=attempt.status,
                        )
                        for attempt in attempts
                    ),
                    external_runs=external_runs,
                    output=(checkpoint.output if checkpoint is not None else None),
                    output_digest=(checkpoint.digest if checkpoint is not None else None),
                    output_recorded_at=(
                        checkpoint.recorded_at.isoformat()
                        if checkpoint is not None
                        else None
                    ),
                )
            )

        return RunManifest(
            schema_version=MANIFEST_SCHEMA_VERSION,
            workflow_run_id=run.run_id,
            workflow_name=run.workflow_name,
            workflow_version=run.workflow_version,
            definition_fingerprint=run.definition_fingerprint,
            plan_fingerprint=run.plan_fingerprint,
            status=run.status,
            created_at=run.created_at.isoformat(),
            started_at=run.started_at.isoformat() if run.started_at is not None else None,
            ended_at=run.ended_at.isoformat() if run.ended_at is not None else None,
            tasks=tuple(tasks),
            events=tuple(self._metadata.list_runtime_events(workflow_run_id)),
        )


__all__ = ["MANIFEST_SCHEMA_VERSION", "RunManifestBuilder"]
