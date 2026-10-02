"""Canonical V2 workflow planner."""

from __future__ import annotations

from collections.abc import Mapping

from pyworkflowkit.authoring import (
    RegisteredWorkload,
    TaskDefinition,
    WorkflowDefinition,
    WorkloadDescriptor,
)
from pyworkflowkit.authoring.workloads import (
    workload_fingerprint_payload,
    workload_portability,
)
from pyworkflowkit.diagnostics import Diagnostic, DiagnosticSeverity
from pyworkflowkit.planning._graph import _DependencyGraph
from pyworkflowkit.planning.model import (
    ExecutionPlan,
    ExecutorRequirement,
    TaskPlanEntry,
)


class WorkflowPlanner:
    """Compile immutable authoring declarations into deterministic execution plans."""

    def compile(self, workflow: WorkflowDefinition) -> ExecutionPlan:
        """Compile without allocating runtime identity or executing workload code."""

        if not isinstance(workflow, WorkflowDefinition):
            raise TypeError("workflow must be a V2 WorkflowDefinition")

        workflow.validate()
        graph = _DependencyGraph(workflow)
        groups = graph.topological_layers()
        topological_order = tuple(task_key for group in groups for task_key in group)
        definitions = {task.key: task for task in workflow.tasks}

        diagnostics: list[Diagnostic] = [
            Diagnostic(
                code="PWK-PLAN-001",
                severity=DiagnosticSeverity.INFO,
                summary="workflow topology validated",
                details=(
                    ("task_count", str(len(workflow.tasks))),
                    ("edge_count", str(len(graph.edges))),
                ),
                source_component="planning",
                decision_context="compile",
            )
        ]

        entries: list[TaskPlanEntry] = []
        capabilities: set[str] = set()
        integrations: set[str] = set()
        position = 0

        for group_index, group in enumerate(groups):
            for task_key in group:
                task = definitions[task_key]
                requirement = _executor_requirement(task)
                task_integrations = _integration_requirements(task)

                capabilities.add(f"executor:{requirement.executor_key}")
                capabilities.add(f"workload:{requirement.workload_kind}")
                integrations.update(task_integrations)

                if not requirement.portable:
                    diagnostics.append(
                        Diagnostic(
                            code="PWK-PLAN-PORTABILITY-001",
                            severity=DiagnosticSeverity.WARNING,
                            summary="task workload is process-local and non-portable",
                            details=(("task_key", task.key),),
                            source_component="planning",
                            decision_context="portability",
                        )
                    )

                entries.append(
                    TaskPlanEntry(
                        task=task,
                        position=position,
                        group_index=group_index,
                        executor_requirement=requirement,
                        required_integrations=task_integrations,
                    )
                )
                position += 1

        return ExecutionPlan(
            workflow_name=workflow.name,
            workflow_version=workflow.version,
            definition_fingerprint=workflow.fingerprint(),
            failure_policy=workflow.failure_policy,
            tasks=tuple(entries),
            topological_order=topological_order,
            groups=groups,
            required_capabilities=tuple(capabilities),
            required_integrations=tuple(integrations),
            diagnostics=tuple(diagnostics),
        )


def _executor_requirement(task: TaskDefinition) -> ExecutorRequirement:
    workload = task.workload
    portability = workload_portability(workload)
    payload = workload_fingerprint_payload(workload)
    workload_kind = _payload_kind(payload)

    executor_key = "inline"
    if isinstance(workload, RegisteredWorkload):
        executor_key = workload.executor_key or executor_key
    elif isinstance(workload, WorkloadDescriptor):
        declared_executor = getattr(workload, "executor_key", None)
        if declared_executor is not None:
            if not isinstance(declared_executor, str) or not declared_executor.strip():
                raise ValueError(f"task {task.key!r} declares an invalid executor_key")
            executor_key = declared_executor

    return ExecutorRequirement(
        executor_key=executor_key,
        workload_kind=workload_kind,
        portable=portability.value == "portable",
    )


def _payload_kind(payload: Mapping[str, object]) -> str:
    value = payload.get("kind", "unknown")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("workload fingerprint payload kind must be a non-empty string")
    return value


def _integration_requirements(task: TaskDefinition) -> tuple[str, ...]:
    workload = task.workload
    requirements: set[str] = set()

    if isinstance(workload, WorkloadDescriptor):
        explicit = getattr(workload, "integration_key", None)
        if explicit is not None:
            if not isinstance(explicit, str) or not explicit.strip():
                raise ValueError(f"task {task.key!r} declares an invalid integration_key")
            requirements.add(explicit)

        kind = workload.workload_kind.lower()
        if kind.startswith("pyingestkit"):
            requirements.add("pyingestkit")
        if kind.startswith("pytransformkit"):
            requirements.add("pytransformkit")

    return tuple(sorted(requirements))


__all__ = ["WorkflowPlanner"]
