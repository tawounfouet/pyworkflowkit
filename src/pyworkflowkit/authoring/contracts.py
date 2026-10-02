"""Machine-readable LOT-02 qualified authoring API contract."""

from __future__ import annotations

V2_AUTHORING_API_CONTRACT_VERSION = "1"

V2_AUTHORING_PUBLIC_SURFACE: tuple[str, ...] = (
    "InputDeclaration",
    "OutputDeclaration",
    "RegisteredWorkload",
    "TaskDefinition",
    "WorkflowDefinition",
    "WorkflowDefinitionBuilder",
    "WorkflowTemplate",
    "WorkloadDescriptor",
    "WorkloadPortability",
    "task",
    "workflow",
)

V2_TASK_DEFINITION_FIELDS: tuple[str, ...] = (
    "key",
    "workload",
    "dependencies",
    "retry_policy",
    "timeout_policy",
    "trigger_rule",
    "inputs",
    "outputs",
    "metadata",
)

V2_WORKFLOW_DEFINITION_FIELDS: tuple[str, ...] = (
    "name",
    "tasks",
    "version",
    "failure_policy",
    "metadata",
)


def v2_authoring_contract_snapshot() -> dict[str, object]:
    return {
        "contract_version": V2_AUTHORING_API_CONTRACT_VERSION,
        "surface": list(V2_AUTHORING_PUBLIC_SURFACE),
        "task_definition_fields": list(V2_TASK_DEFINITION_FIELDS),
        "workflow_definition_fields": list(V2_WORKFLOW_DEFINITION_FIELDS),
    }


__all__ = [
    "V2_AUTHORING_API_CONTRACT_VERSION",
    "V2_AUTHORING_PUBLIC_SURFACE",
    "V2_TASK_DEFINITION_FIELDS",
    "V2_WORKFLOW_DEFINITION_FIELDS",
    "v2_authoring_contract_snapshot",
]
