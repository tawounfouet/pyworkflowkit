"""Small public-facing workflow runtime facade."""

from __future__ import annotations

from collections.abc import Mapping

from pyworkflowkit.application.factory import RuntimeComponents, RuntimeFactory
from pyworkflowkit.application.lineage import ExecutionLineageProjector
from pyworkflowkit.application.manifest import RunManifestBuilder
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.domain.definitions import WorkflowDefinition
from pyworkflowkit.domain.ids import WorkflowRunId
from pyworkflowkit.domain.lineage import ExecutionLineage
from pyworkflowkit.domain.manifest import RunManifest
from pyworkflowkit.domain.runtime import RuntimeEvent, WorkflowRun
from pyworkflowkit.ports.executor import TaskHandler


class WorkflowRuntime:
    """Stable application facade for defining handler bindings and executing workflows."""

    def __init__(self, settings: RuntimeSettings | None = None) -> None:
        self._components: RuntimeComponents = RuntimeFactory.build(settings)

    @property
    def settings(self) -> RuntimeSettings:
        return self._components.settings

    def register(self, handler_ref: str, handler: TaskHandler) -> None:
        """Register one callable under an explicit handler reference."""

        self._components.handler_registry.register(handler_ref, handler)

    def run(
        self,
        workflow: WorkflowDefinition,
        *,
        parameters: Mapping[str, object] | None = None,
    ) -> WorkflowRun:
        """Execute one workflow synchronously."""

        return self._components.runner.run(workflow, parameters=parameters)

    def get_run(self, run_id: WorkflowRunId | str) -> WorkflowRun:
        """Load one persisted workflow run."""

        return self._components.metadata_store.get_workflow_run(WorkflowRunId(str(run_id)))

    def events(self, run_id: WorkflowRunId | str) -> tuple[RuntimeEvent, ...]:
        """Return persisted runtime events in durable sequence order."""

        return self._components.metadata_store.list_events(WorkflowRunId(str(run_id)))

    def manifest(
        self,
        workflow: WorkflowDefinition,
        run_id: WorkflowRunId | str,
    ) -> RunManifest:
        """Build final portable evidence for a terminal run."""

        return RunManifestBuilder(metadata_store=self._components.metadata_store).build(
            workflow=workflow,
            run_id=WorkflowRunId(str(run_id)),
        )

    def lineage(
        self,
        workflow: WorkflowDefinition,
        run_id: WorkflowRunId | str,
    ) -> ExecutionLineage:
        """Project deterministic execution lineage for one run."""

        return ExecutionLineageProjector(metadata_store=self._components.metadata_store).project(
            workflow=workflow,
            run_id=WorkflowRunId(str(run_id)),
        )


__all__ = ["WorkflowRuntime"]
