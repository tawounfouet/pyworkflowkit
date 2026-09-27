"""WorkflowRuntime-backed implementation of the control-plane provider contract."""

from __future__ import annotations

from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version

from pyworkflowkit.domain.lineage import ExecutionLineage
from pyworkflowkit.application.manifest import RunManifestSerializer
from pyworkflowkit.application.mapping import DomainSchemaMapper
from pyworkflowkit.application.observability import redact_mapping
from pyworkflowkit.application.planning import (
    DAGValidator,
    ExecutionPlanner,
    build_dependency_graph,
)
from pyworkflowkit.application.reconciliation import ReconciliationReport
from pyworkflowkit.application.recovery import RecoveryAssessment
from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.contracts.serialization import (
    RuntimeEventSchema,
    WorkflowDefinitionSchema,
    normalize_portable_json_value,
)
from pyworkflowkit.control_plane.contracts import (
    CONTROL_PLANE_OPERATIONS,
    CONTROL_PLANE_PROVIDER_CONTRACT_VERSION,
    ControlPlaneOperation,
    ControlPlaneRunSchema,
    ExecutionGroupSchema,
    ExecutionLineageSchema,
    ExternalRunObservationSchema,
    LineageDependencySchema,
    ProviderCapabilitiesSchema,
    ReconciliationReportSchema,
    RecoveryAssessmentSchema,
    TaskExecutionLineageSchema,
    TaskIdempotencySchema,
    TaskReconciliationSchema,
    WorkflowInspectionSchema,
    WorkflowValidationResultSchema,
)
from pyworkflowkit.domain.definitions import WorkflowDefinition
from pyworkflowkit.domain.runtime import RuntimeEvent, WorkflowRun
from pyworkflowkit.errors import (
    ControlPlaneCapabilityError,
    PyWorkflowKitError,
)


def _runtime_version() -> str:
    try:
        return version("pyworkflowkit")
    except PackageNotFoundError:  # pragma: no cover - source-tree fallback
        return "0.0.0+unknown"


def _workflow_schema(
    workflow: WorkflowDefinitionSchema | Mapping[str, object],
) -> WorkflowDefinitionSchema:
    if isinstance(workflow, WorkflowDefinitionSchema):
        return workflow
    return WorkflowDefinitionSchema.model_validate(dict(workflow))


def _workflow_definition(
    workflow: WorkflowDefinitionSchema | Mapping[str, object],
) -> WorkflowDefinition:
    return DomainSchemaMapper.workflow_definition_from_schema(_workflow_schema(workflow))


def _run_schema(run: WorkflowRun) -> ControlPlaneRunSchema:
    return ControlPlaneRunSchema(
        run_id=str(run.run_id),
        workflow_id=str(run.workflow_id),
        workflow_version=run.workflow_version,
        status=run.status.value,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _event_schema(event: RuntimeEvent) -> RuntimeEventSchema:
    schema = DomainSchemaMapper.runtime_event_to_schema(event)
    return schema.model_copy(update={"payload": redact_mapping(schema.payload)})


def _lineage_schema(lineage: ExecutionLineage) -> ExecutionLineageSchema:
    return ExecutionLineageSchema(
        run_id=lineage.run_id,
        workflow_id=lineage.workflow_id,
        workflow_version=lineage.workflow_version,
        tasks=tuple(
            TaskExecutionLineageSchema(
                task_id=task.task_id,
                task_run_id=task.task_run_id,
                attempt_ids=task.attempt_ids,
                artifact_ids=task.artifact_ids,
                external_ref_ids=task.external_ref_ids,
            )
            for task in lineage.tasks
        ),
        dependencies=tuple(
            LineageDependencySchema(
                upstream_task_run_id=dependency.upstream_task_run_id,
                downstream_task_run_id=dependency.downstream_task_run_id,
            )
            for dependency in lineage.dependencies
        ),
    )


def _recovery_schema(assessment: RecoveryAssessment) -> RecoveryAssessmentSchema:
    return RecoveryAssessmentSchema(
        run_id=assessment.run_id,
        workflow_id=assessment.workflow_id,
        workflow_version=assessment.workflow_version,
        workflow_status=assessment.workflow_status.value,
        observed_at=assessment.observed_at,
        last_evidence_at=assessment.last_evidence_at,
        stale_after_seconds=assessment.stale_after_seconds,
        liveness=assessment.liveness.value,
        resume_eligibility=assessment.resume_eligibility.value,
        running_task_run_ids=assessment.running_task_run_ids,
        running_attempt_ids=assessment.running_attempt_ids,
        retry_waiting_task_run_ids=assessment.retry_waiting_task_run_ids,
        next_retry_eligible_at=assessment.next_retry_eligible_at,
        external_run_ref_count=assessment.external_run_ref_count,
        unresolved_external_run_ref_count=assessment.unresolved_external_run_ref_count,
        idempotency=tuple(
            TaskIdempotencySchema(
                task_id=item.task_id,
                task_run_id=item.task_run_id,
                idempotency_key=item.idempotency_key,
                attempt_count=item.attempt_count,
            )
            for item in assessment.idempotency
        ),
        reasons=assessment.reasons,
    )


def _reconciliation_schema(report: ReconciliationReport) -> ReconciliationReportSchema:
    return ReconciliationReportSchema(
        run_id=report.run_id,
        task_reconciliations=tuple(
            TaskReconciliationSchema(
                task_run_id=item.task_run_id,
                task_id=item.task_id,
                disposition=item.disposition.value,
                running_attempt_ids=item.running_attempt_ids,
                observations=tuple(
                    ExternalRunObservationSchema(
                        external_ref_id=observation.external_ref_id,
                        provider=observation.provider,
                        external_run_id=observation.external_run_id,
                        status=observation.status.value,
                        reason=observation.reason,
                    )
                    for observation in item.observations
                ),
                reasons=item.reasons,
            )
            for item in report.task_reconciliations
        ),
        fully_resolved=report.fully_resolved,
        has_still_running=report.has_still_running,
        requires_manual_action=report.requires_manual_action,
    )


class WorkflowRuntimeProvider:
    """Operate one configured WorkflowRuntime through portable control-plane contracts.

    Handler registration, executor construction, persistence configuration and verifier
    registration remain host responsibilities. The provider deliberately exposes none of
    those implementation objects to the control plane.
    """

    def __init__(
        self,
        runtime: WorkflowRuntime,
        *,
        provider_name: str = "pyworkflowkit.local",
    ) -> None:
        if not isinstance(provider_name, str) or not provider_name.strip():
            raise ValueError("provider_name must be a non-empty string")
        self._runtime = runtime
        self._provider_name = provider_name

    def inspect_capabilities(self) -> ProviderCapabilitiesSchema:
        """Describe supported operations without exposing executor/store instances."""

        operations = {operation: True for operation in CONTROL_PLANE_OPERATIONS}
        operations[ControlPlaneOperation.REQUEST_CANCELLATION.value] = False
        return ProviderCapabilitiesSchema(
            contract_version=CONTROL_PLANE_PROVIDER_CONTRACT_VERSION,
            provider_name=self._provider_name,
            runtime_version=_runtime_version(),
            operations=operations,
            scheduling_owned_by_control_plane=True,
            background_execution=False,
        )

    def validate_workflow(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
    ) -> WorkflowValidationResultSchema:
        """Validate portable definition/schema and DAG invariants without execution."""

        workflow_id: str | None = None
        workflow_version: str | None = None
        task_count = 0
        if isinstance(workflow, WorkflowDefinitionSchema):
            workflow_id = workflow.workflow_id
            workflow_version = workflow.version
            task_count = len(workflow.tasks)
        else:
            raw_id = workflow.get("workflow_id")
            raw_version = workflow.get("version")
            raw_tasks = workflow.get("tasks")
            workflow_id = raw_id if isinstance(raw_id, str) else None
            workflow_version = raw_version if isinstance(raw_version, str) else None
            task_count = len(raw_tasks) if isinstance(raw_tasks, (list, tuple)) else 0

        try:
            definition = _workflow_definition(workflow)
            graph = build_dependency_graph(definition)
            DAGValidator().validate(definition, graph)
            ExecutionPlanner().build_plan(definition, graph)
        except (PyWorkflowKitError, TypeError, ValueError) as exc:
            return WorkflowValidationResultSchema(
                valid=False,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
                task_count=task_count,
                diagnostics=(f"{type(exc).__name__}: {exc}",),
            )

        return WorkflowValidationResultSchema(
            valid=True,
            workflow_id=str(definition.workflow_id),
            workflow_version=definition.version,
            task_count=len(definition.tasks),
        )

    def inspect_workflow(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
    ) -> WorkflowInspectionSchema:
        """Return canonical definition plus deterministic topological plan."""

        schema = _workflow_schema(workflow)
        definition = DomainSchemaMapper.workflow_definition_from_schema(schema)
        graph = build_dependency_graph(definition)
        DAGValidator().validate(definition, graph)
        plan = ExecutionPlanner().build_plan(definition, graph)
        return WorkflowInspectionSchema(
            definition=schema,
            task_order=tuple(str(task.task_id) for task in plan.tasks),
            groups=tuple(
                ExecutionGroupSchema(
                    index=group.index,
                    task_ids=tuple(str(task_id) for task_id in group.task_ids),
                )
                for group in plan.groups
            ),
        )

    def execute_workflow(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
        *,
        parameters: dict[str, object] | None = None,
    ) -> ControlPlaneRunSchema:
        """Execute one workflow synchronously through the configured runtime."""

        definition = _workflow_definition(workflow)
        normalized_parameters = _portable_parameters(parameters)
        return _run_schema(self._runtime.run(definition, parameters=normalized_parameters))

    def inspect_run(self, run_id: str) -> ControlPlaneRunSchema:
        """Return a persisted run summary without exposing raw parameters."""

        return _run_schema(self._runtime.get_run(run_id))

    def list_runtime_events(self, run_id: str) -> tuple[RuntimeEventSchema, ...]:
        """Return committed events with defensive sensitive-key redaction."""

        return tuple(_event_schema(event) for event in self._runtime.events(run_id))

    def retrieve_manifest(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
        run_id: str,
    ) -> dict[str, object]:
        """Return canonical RunManifest evidence governed by manifest schema v1."""

        manifest = self._runtime.manifest(_workflow_definition(workflow), run_id)
        return RunManifestSerializer().to_dict(manifest)

    def retrieve_lineage(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
        run_id: str,
    ) -> ExecutionLineageSchema:
        """Return deterministic lineage without exposing MetadataStore internals."""

        lineage = self._runtime.lineage(_workflow_definition(workflow), run_id)
        return _lineage_schema(lineage)

    def request_cancellation(self, run_id: str, *, reason: str | None = None) -> None:
        """Reject cancellation because WorkflowRuntime has no external cancel command."""

        del run_id, reason
        raise ControlPlaneCapabilityError(
            operation=ControlPlaneOperation.REQUEST_CANCELLATION.value,
            reason=(
                "WorkflowRuntimeProvider executes synchronously and does not expose an "
                "external cancellation command"
            ),
        )

    def assess_recovery(
        self,
        run_id: str,
        *,
        stale_after_seconds: float = 300.0,
    ) -> RecoveryAssessmentSchema:
        """Return read-only durable recovery classification."""

        return _recovery_schema(
            self._runtime.recovery_assessment(
                run_id,
                stale_after_seconds=stale_after_seconds,
            )
        )

    def reconcile_run(
        self,
        run_id: str,
        *,
        stale_after_seconds: float = 300.0,
    ) -> ReconciliationReportSchema:
        """Return provider-normalized read-only reconciliation evidence."""

        return _reconciliation_schema(
            self._runtime.reconcile_run(
                run_id,
                stale_after_seconds=stale_after_seconds,
            )
        )

    def resume_run(
        self,
        workflow: WorkflowDefinitionSchema | dict[str, object],
        run_id: str,
        *,
        stale_after_seconds: float = 300.0,
    ) -> ControlPlaneRunSchema:
        """Resume one eligible run using the existing runtime recovery semantics."""

        resumed = self._runtime.resume_run(
            _workflow_definition(workflow),
            run_id,
            stale_after_seconds=stale_after_seconds,
        )
        return _run_schema(resumed)


def _portable_parameters(
    parameters: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if parameters is None:
        return None
    normalized = normalize_portable_json_value(
        parameters,
        path="control_plane.parameters",
    )
    if not isinstance(normalized, dict):
        raise TypeError("control-plane parameter normalization must return a dict")
    return normalized


__all__ = ["WorkflowRuntimeProvider"]
