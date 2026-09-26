"""Small public-facing workflow runtime facade."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

from pyworkflowkit.application.factory import RuntimeComponents, RuntimeFactory
from pyworkflowkit.application.inspection import RuntimeInspection, RuntimeInspector
from pyworkflowkit.application.lineage import ExecutionLineageProjector
from pyworkflowkit.application.manifest import RunManifestBuilder
from pyworkflowkit.application.observability_plugins import ObservabilityDispatchFailure
from pyworkflowkit.application.reconciliation import ReconciliationReport, ReconciliationService
from pyworkflowkit.application.recovery import RecoveryAssessment, RecoveryInspector
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.domain.definitions import WorkflowDefinition
from pyworkflowkit.domain.ids import WorkflowRunId
from pyworkflowkit.domain.lineage import ExecutionLineage
from pyworkflowkit.domain.manifest import RunManifest
from pyworkflowkit.domain.runtime import RuntimeEvent, WorkflowRun
from pyworkflowkit.ports.executor import TaskHandler
from pyworkflowkit.ports.observability import RuntimeEventSink
from pyworkflowkit.ports.reconciliation import ExternalRunVerifier


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

    def register_event_sink(self, sink: RuntimeEventSink) -> None:
        """Register one committed-runtime-event observability sink."""

        self._components.observability.register(sink)

    def register_external_run_verifier(self, verifier: ExternalRunVerifier) -> None:
        """Register one provider-specific external-run status verifier."""

        self._components.reconciliation_verifiers.register(verifier)

    @property
    def observability_failures(self) -> tuple[ObservabilityDispatchFailure, ...]:
        """Return isolated observability sink failures."""

        return self._components.observability.failures

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

        return tuple(self._components.metadata_store.list_events(WorkflowRunId(str(run_id))))

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

    def inspect_runtime(
        self,
        workflow: WorkflowDefinition,
        run_id: WorkflowRunId | str,
    ) -> RuntimeInspection:
        """Build a structured runtime diagnostic snapshot."""

        return RuntimeInspector(metadata_store=self._components.metadata_store).inspect(
            workflow=workflow,
            run_id=WorkflowRunId(str(run_id)),
        )

    def recovery_assessment(
        self,
        run_id: WorkflowRunId | str,
        *,
        stale_after_seconds: float = 300.0,
    ) -> RecoveryAssessment:
        """Classify persisted recovery evidence without mutating the run."""

        return RecoveryInspector(
            metadata_store=self._components.metadata_store,
            clock=self._components.clock,
            stale_after=timedelta(seconds=stale_after_seconds),
        ).assess(WorkflowRunId(str(run_id)))

    def stale_run_candidates(
        self,
        *,
        stale_after_seconds: float = 300.0,
    ) -> tuple[RecoveryAssessment, ...]:
        """Return persisted non-terminal runs whose evidence is stale."""

        return RecoveryInspector(
            metadata_store=self._components.metadata_store,
            clock=self._components.clock,
            stale_after=timedelta(seconds=stale_after_seconds),
        ).find_stale_candidates()

    def reconcile_run(
        self,
        run_id: WorkflowRunId | str,
        *,
        stale_after_seconds: float = 300.0,
    ) -> ReconciliationReport:
        """Verify ambiguous external work without mutating persisted runtime state."""

        return ReconciliationService(
            metadata_store=self._components.metadata_store,
            clock=self._components.clock,
            verifier_registry=self._components.reconciliation_verifiers,
            stale_after=timedelta(seconds=stale_after_seconds),
        ).reconcile(WorkflowRunId(str(run_id)))

    def resume_run(
        self,
        workflow: WorkflowDefinition,
        run_id: WorkflowRunId | str,
        *,
        stale_after_seconds: float = 300.0,
    ) -> WorkflowRun:
        """Resume one stale persisted WorkflowRun after reconciliation."""

        resolved_run_id = WorkflowRunId(str(run_id))
        reconciliation = ReconciliationService(
            metadata_store=self._components.metadata_store,
            clock=self._components.clock,
            verifier_registry=self._components.reconciliation_verifiers,
            stale_after=timedelta(seconds=stale_after_seconds),
        ).reconcile(resolved_run_id)
        return self._components.runner.resume(
            workflow,
            run_id=resolved_run_id,
            reconciliation=reconciliation,
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
