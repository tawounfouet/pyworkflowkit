"""LOT-03 reference acceptance for canonical V2 planning."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit._compat.v1_root as v1_root
import pyworkflowkit.planning as planning
from pyworkflowkit.application.planning import ExecutionPlan as LegacyExecutionPlan
from pyworkflowkit.authoring import RegisteredWorkload, TaskDefinition, WorkflowDefinition
from pyworkflowkit.planning import ExecutionPlan, WorkflowPlanner
from pyworkflowkit.planning.contracts import (
    V2_EXECUTION_PLAN_FIELDS,
    V2_PLANNING_PUBLIC_SURFACE,
    v2_planning_contract_snapshot,
)


def test_qualified_planning_surface_matches_lot03_contract() -> None:
    assert tuple(planning.__all__) == V2_PLANNING_PUBLIC_SURFACE

    snapshot = v2_planning_contract_snapshot()
    assert snapshot["contract_version"] == "1"
    assert snapshot["execution_plan_fields"] == list(V2_EXECUTION_PLAN_FIELDS)


def test_lot03_execution_plan_replaces_legacy_qualified_shape_only() -> None:
    plan = WorkflowPlanner().compile(
        WorkflowDefinition(
            name="demo",
            tasks=(
                TaskDefinition(
                    key="fetch",
                    workload=RegisteredWorkload("jobs.fetch"),
                ),
            ),
        )
    )

    assert isinstance(plan, ExecutionPlan)
    assert not isinstance(plan, LegacyExecutionPlan)
    assert plan.workflow_name == "demo"
    assert not hasattr(plan, "workflow_id")


def test_lot22_promotes_planning_to_root_without_mutating_v1_facade() -> None:
    assert pyworkflowkit.ExecutionPlan is ExecutionPlan
    assert "ExecutionPlan" not in v1_root.__all__


def test_graph_internals_are_not_public_planning_exports() -> None:
    assert "DependencyGraph" not in planning.__all__
    assert "WorkflowGraph" not in planning.__all__
    assert "_DependencyGraph" not in planning.__all__


def test_compilation_allocates_no_runtime_identity() -> None:
    plan = WorkflowPlanner().compile(
        WorkflowDefinition(
            name="identity_free",
            tasks=(
                TaskDefinition(
                    key="fetch",
                    workload=RegisteredWorkload("jobs.fetch"),
                ),
            ),
        )
    )

    assert not hasattr(plan, "workflow_run_id")
    assert not hasattr(plan.task("fetch"), "task_run_id")
    assert not hasattr(plan.task("fetch"), "task_attempt_id")
