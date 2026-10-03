"""Canonical V2 execution-lineage projection."""

from __future__ import annotations

from pyworkflowkit.authoring import WorkflowDefinition
from pyworkflowkit.errors import MetadataNotFoundError, RuntimeInvariantError
from pyworkflowkit.lineage.model import (
    ExecutionLineage,
    LineageDependency,
    TaskExecutionLineage,
)
from pyworkflowkit.persistence import MetadataStore
from pyworkflowkit.planning import ExecutionPlan, WorkflowPlanner
from pyworkflowkit.runtime.identity import WorkflowRunId


class ExecutionLineageProjector:
    """Project execution provenance from one plan plus durable runtime evidence."""

    def __init__(
        self,
        *,
        metadata: MetadataStore,
        planner: WorkflowPlanner | None = None,
    ) -> None:
        if not isinstance(metadata, MetadataStore):
            raise TypeError("metadata must satisfy the V2 MetadataStore Protocol")
        self._metadata = metadata
        self._planner = planner or WorkflowPlanner()

    def project(
        self,
        workflow: WorkflowDefinition | ExecutionPlan,
        workflow_run_id: WorkflowRunId,
    ) -> ExecutionLineage:
        plan = (
            self._planner.compile(workflow)
            if isinstance(workflow, WorkflowDefinition)
            else workflow
        )
        if not isinstance(plan, ExecutionPlan):
            raise TypeError("workflow must be WorkflowDefinition or ExecutionPlan")

        run = self._metadata.get_workflow_run(workflow_run_id)
        if (
            run.workflow_name != plan.workflow_name
            or run.workflow_version != plan.workflow_version
            or run.definition_fingerprint != plan.definition_fingerprint
            or run.plan_fingerprint != plan.fingerprint()
        ):
            raise RuntimeInvariantError(
                reason="execution plan does not match persisted WorkflowRun identity"
            )

        task_runs = tuple(self._metadata.list_task_runs(workflow_run_id))
        by_key = {task_run.task_key: task_run for task_run in task_runs}
        expected = set(plan.topological_order)
        if set(by_key) != expected:
            raise RuntimeInvariantError(
                reason="lineage projection task set does not match ExecutionPlan"
            )

        tasks: list[TaskExecutionLineage] = []
        for key in plan.topological_order:
            task_run = by_key[key]
            attempts = tuple(self._metadata.list_task_attempts(task_run.task_run_id))
            external_runs = tuple(
                ref
                for attempt in attempts
                for ref in self._metadata.list_external_run_refs(attempt.attempt_id)
            )
            try:
                checkpoint = self._metadata.get_task_output_checkpoint(task_run.task_run_id)
            except MetadataNotFoundError:
                checkpoint = None
            tasks.append(
                TaskExecutionLineage(
                    task_key=key,
                    task_run_id=task_run.task_run_id,
                    attempt_ids=tuple(attempt.attempt_id for attempt in attempts),
                    external_runs=external_runs,
                    output_digest=checkpoint.digest if checkpoint is not None else None,
                )
            )

        dependencies: list[LineageDependency] = []
        for entry in plan.tasks:
            downstream = by_key[entry.key]
            for upstream_key in entry.dependencies:
                dependencies.append(
                    LineageDependency(
                        upstream_task_run_id=by_key[upstream_key].task_run_id,
                        downstream_task_run_id=downstream.task_run_id,
                    )
                )

        return ExecutionLineage(
            workflow_run_id=run.run_id,
            workflow_name=run.workflow_name,
            workflow_version=run.workflow_version,
            definition_fingerprint=run.definition_fingerprint,
            plan_fingerprint=run.plan_fingerprint,
            tasks=tuple(tasks),
            dependencies=tuple(dependencies),
        )


__all__ = ["ExecutionLineageProjector"]
