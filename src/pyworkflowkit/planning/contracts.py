"""Machine-readable LOT-03 qualified planning API contract."""

from __future__ import annotations

V2_PLANNING_API_CONTRACT_VERSION = "1"

V2_PLANNING_PUBLIC_SURFACE: tuple[str, ...] = (
    "ExecutionPlan",
    "ExecutorRequirement",
    "TaskPlanEntry",
    "WorkflowPlanner",
)

V2_EXECUTION_PLAN_FIELDS: tuple[str, ...] = (
    "workflow_name",
    "workflow_version",
    "definition_fingerprint",
    "failure_policy",
    "tasks",
    "topological_order",
    "groups",
    "required_capabilities",
    "required_integrations",
    "diagnostics",
)


def v2_planning_contract_snapshot() -> dict[str, object]:
    return {
        "contract_version": V2_PLANNING_API_CONTRACT_VERSION,
        "surface": list(V2_PLANNING_PUBLIC_SURFACE),
        "execution_plan_fields": list(V2_EXECUTION_PLAN_FIELDS),
    }


__all__ = [
    "V2_EXECUTION_PLAN_FIELDS",
    "V2_PLANNING_API_CONTRACT_VERSION",
    "V2_PLANNING_PUBLIC_SURFACE",
    "v2_planning_contract_snapshot",
]
