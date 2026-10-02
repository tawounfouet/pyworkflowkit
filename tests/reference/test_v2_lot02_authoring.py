"""LOT-02 reference acceptance for canonical V2 authoring."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.authoring as authoring
from pyworkflowkit.authoring import (
    RegisteredWorkload,
    TaskDefinition,
    WorkflowDefinition,
)
from pyworkflowkit.authoring.contracts import (
    V2_AUTHORING_PUBLIC_SURFACE,
    V2_TASK_DEFINITION_FIELDS,
    V2_WORKFLOW_DEFINITION_FIELDS,
    v2_authoring_contract_snapshot,
)
from pyworkflowkit.domain.definitions import (
    TaskDefinition as LegacyTaskDefinition,
)
from pyworkflowkit.domain.definitions import (
    WorkflowDefinition as LegacyWorkflowDefinition,
)


def test_qualified_authoring_surface_matches_lot02_contract() -> None:
    assert tuple(authoring.__all__) == V2_AUTHORING_PUBLIC_SURFACE

    snapshot = v2_authoring_contract_snapshot()
    assert snapshot["contract_version"] == "1"
    assert snapshot["task_definition_fields"] == list(V2_TASK_DEFINITION_FIELDS)
    assert snapshot["workflow_definition_fields"] == list(V2_WORKFLOW_DEFINITION_FIELDS)


def test_lot02_authoring_is_canonical_v2_not_legacy_definition_shape() -> None:
    assert TaskDefinition is not LegacyTaskDefinition
    assert WorkflowDefinition is not LegacyWorkflowDefinition

    task = TaskDefinition(
        key="fetch",
        workload=RegisteredWorkload("jobs.fetch"),
    )
    workflow = WorkflowDefinition(name="demo", tasks=(task,))

    assert task.key == "fetch"
    assert workflow.name == "demo"
    assert not hasattr(task, "task_id")
    assert not hasattr(task, "handler_ref")


def test_frozen_1_1_root_still_exports_legacy_definitions() -> None:
    assert pyworkflowkit.TaskDefinition is LegacyTaskDefinition
    assert pyworkflowkit.WorkflowDefinition is LegacyWorkflowDefinition


def test_no_public_graph_is_required_for_v2_authoring() -> None:
    assert "WorkflowGraph" not in authoring.__all__
    assert "DependencyGraph" not in authoring.__all__
