"""LOT-19 reference acceptance for canonical V2 PyTransformKit integration."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.integrations.pytransformkit as pytransformkit
from pyworkflowkit.authoring import RegisteredWorkload, WorkflowDefinition
from pyworkflowkit.integrations.pytransformkit import (
    PyTransformKitResourceReference,
    PyTransformKitWorkload,
    pytransformkit_v2_task,
)
from pyworkflowkit.planning import WorkflowPlanner


def test_lot19_surface_is_qualified_without_root_promotion() -> None:
    required = {
        "PyTransformKitExecutionJob",
        "PyTransformKitExecutionResult",
        "PyTransformKitExecutionStatus",
        "PyTransformKitResourceReference",
        "PyTransformKitRetryOwner",
        "PyTransformKitWorkload",
        "PyTransformKitWorkloadHandler",
        "pytransformkit_v2_task",
        "pytransformkit_v2_workload_binding",
        "v2_pytransformkit_integration_snapshot",
    }

    assert required.issubset(set(pytransformkit.__all__))
    for name in required:
        assert name not in pyworkflowkit.__all__


def test_lot19_descriptor_uses_registered_workload_and_explicit_integration() -> None:
    workload = PyTransformKitWorkload(plan_ref="customer360.plan")

    assert isinstance(workload, RegisteredWorkload)
    assert workload.registry_key == "pytransformkit:customer360.plan"
    assert workload.integration_key == "pytransformkit"


def test_lot19_resource_reference_is_data_only() -> None:
    resource = PyTransformKitResourceReference(
        resource_id="customer360-v1",
        uri="resource://customer360/v1",
        metadata=(("format", "parquet"),),
    )

    assert resource.as_portable_output() == {
        "kind": "pytransformkit.resource_reference",
        "resource_id": "customer360-v1",
        "uri": "resource://customer360/v1",
        "version": None,
        "metadata": {"format": "parquet"},
        "contract_version": "1",
    }


def test_lot19_planner_records_pytransformkit_requirement() -> None:
    upstream = pytransformkit_v2_task(
        key="transform_customer_360",
        plan_ref="customer360.plan",
    )
    plan = WorkflowPlanner().compile(WorkflowDefinition(name="lot19-reference", tasks=(upstream,)))

    assert plan.required_integrations == ("pytransformkit",)
    assert plan.task("transform_customer_360").required_integrations == ("pytransformkit",)


def test_lot19_snapshot_freezes_fail_closed_boundary() -> None:
    assert pytransformkit.v2_pytransformkit_integration_snapshot() == {
        "contract_version": "1",
        "integration_key": "pytransformkit",
        "registry_prefix": "pytransformkit:",
        "atomic_plan_boundary": True,
        "imports_pytransformkit": False,
        "workload_base": "RegisteredWorkload",
        "binding_contract": "V2WorkloadBinding",
        "portable_dependency_handoff": True,
        "resource_reference_output": True,
        "external_reference_contract": "ExternalRunRef",
        "unknown_outcome_requires_reconciliation": True,
        "raw_credentials_supported": False,
        "credential_reference_supported": True,
        "implicit_retry_multiplication": False,
    }
