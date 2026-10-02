"""LOT-03 unit tests for the immutable V2 ExecutionPlan."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from pyworkflowkit.authoring import RegisteredWorkload, TaskDefinition, WorkflowDefinition
from pyworkflowkit.planning import ExecutionPlan, WorkflowPlanner


def _plan() -> ExecutionPlan:
    builder = WorkflowDefinition.builder(name="demo")
    fetch = builder.task("fetch", workload=RegisteredWorkload("jobs.fetch"))
    builder.task(
        "publish",
        workload=RegisteredWorkload("jobs.publish"),
        depends_on=(fetch,),
    )
    return WorkflowPlanner().compile(builder.build())


def test_execution_plan_is_immutable() -> None:
    plan = _plan()

    with pytest.raises(FrozenInstanceError):
        plan.workflow_name = "other"  # type: ignore[misc]


def test_execution_plan_contains_no_runtime_identity_or_state_fields() -> None:
    plan_fields = {item.name for item in fields(ExecutionPlan)}
    forbidden = {
        "workflow_run_id",
        "task_run_id",
        "task_attempt_id",
        "attempt_number",
        "status",
        "started_at",
        "ended_at",
    }

    assert forbidden.isdisjoint(plan_fields)


def test_execution_plan_exposes_effective_task_policies() -> None:
    plan = _plan()
    fetch = plan.task("fetch")

    assert fetch.retry_policy is fetch.task.retry_policy
    assert fetch.timeout_policy is fetch.task.timeout_policy
    assert fetch.trigger_rule is fetch.task.trigger_rule


def test_execution_plan_explain_is_deterministic_and_side_effect_free() -> None:
    plan = _plan()

    assert plan.explain() == plan.explain()
    assert "fetch -> publish" in plan.explain()
    assert plan.fingerprint().startswith("sha256:")


def test_execution_plan_rejects_inconsistent_order() -> None:
    plan = _plan()

    with pytest.raises(ValueError, match="topological_order"):
        ExecutionPlan(
            workflow_name=plan.workflow_name,
            workflow_version=plan.workflow_version,
            definition_fingerprint=plan.definition_fingerprint,
            failure_policy=plan.failure_policy,
            tasks=plan.tasks,
            topological_order=tuple(reversed(plan.topological_order)),
            groups=plan.groups,
            required_capabilities=plan.required_capabilities,
            required_integrations=plan.required_integrations,
            diagnostics=plan.diagnostics,
        )
