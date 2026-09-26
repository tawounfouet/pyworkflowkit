"""Build deterministic execution lineage from persisted runtime evidence."""

from pyworkflowkit.domain.definitions import WorkflowDefinition
from pyworkflowkit.domain.ids import WorkflowRunId
from pyworkflowkit.domain.lineage import (
    ExecutionLineage,
    LineageDependency,
    TaskExecutionLineage,
)
from pyworkflowkit.errors import RuntimeInvariantError
from pyworkflowkit.ports.metadata_store import MetadataStore


class ExecutionLineageProjector:
    """Project workflow/runtime relationships without introducing graph persistence."""

    def __init__(self, *, metadata_store: MetadataStore) -> None:
        self._metadata_store = metadata_store

    def project(
        self,
        *,
        workflow: WorkflowDefinition,
        run_id: WorkflowRunId,
    ) -> ExecutionLineage:
        run = self._metadata_store.get_workflow_run(run_id)
        if run.workflow_id != workflow.workflow_id or run.workflow_version != workflow.version:
            raise RuntimeInvariantError(
                reason="workflow definition does not match persisted run identity"
            )

        task_runs = self._metadata_store.list_task_runs(run_id)
        task_runs_by_id = {task_run.task_id: task_run for task_run in task_runs}

        missing = sorted(
            (task.task_id for task in workflow.tasks if task.task_id not in task_runs_by_id),
            key=str,
        )
        if missing:
            rendered = ", ".join(str(task_id) for task_id in missing)
            raise RuntimeInvariantError(
                reason=f"lineage projection is missing TaskRun values for: {rendered}"
            )

        tasks = []
        for task_run in sorted(task_runs, key=lambda value: str(value.task_id)):
            attempts = self._metadata_store.list_task_attempts(task_run.task_run_id)
            artifacts = self._metadata_store.list_artifacts(task_run.task_run_id)
            external_refs = self._metadata_store.list_external_run_refs(task_run.task_run_id)
            tasks.append(
                TaskExecutionLineage(
                    task_id=str(task_run.task_id),
                    task_run_id=str(task_run.task_run_id),
                    attempt_ids=tuple(str(value.attempt_id) for value in attempts),
                    artifact_ids=tuple(str(value.artifact_id) for value in artifacts),
                    external_ref_ids=tuple(
                        str(value.external_ref_id) for value in external_refs
                    ),
                )
            )

        dependencies = []
        for task in sorted(workflow.tasks, key=lambda value: str(value.task_id)):
            downstream = task_runs_by_id[task.task_id]
            for dependency_id in sorted(task.depends_on, key=str):
                upstream = task_runs_by_id.get(dependency_id)
                if upstream is None:
                    raise RuntimeInvariantError(
                        reason=(
                            "lineage projection cannot resolve dependency "
                            f"'{dependency_id}' for task '{task.task_id}'"
                        )
                    )
                dependencies.append(
                    LineageDependency(
                        upstream_task_run_id=str(upstream.task_run_id),
                        downstream_task_run_id=str(downstream.task_run_id),
                    )
                )

        return ExecutionLineage(
            run_id=str(run.run_id),
            workflow_id=str(run.workflow_id),
            workflow_version=run.workflow_version,
            tasks=tuple(tasks),
            dependencies=tuple(dependencies),
        )


__all__ = ["ExecutionLineageProjector"]
