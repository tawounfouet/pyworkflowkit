"""Canonical PyWorkflowKit V2 workflow authoring surface."""

from pyworkflowkit.authoring.builders import WorkflowDefinitionBuilder
from pyworkflowkit.authoring.decorators import WorkflowTemplate, task, workflow
from pyworkflowkit.authoring.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.authoring.io import InputDeclaration, OutputDeclaration
from pyworkflowkit.authoring.workloads import (
    RegisteredWorkload,
    WorkloadDescriptor,
    WorkloadPortability,
)

__all__ = [
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
]
