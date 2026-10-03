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
    workload = PyTransformKitWorkload(
        plan_ref="customer360.plan",
        engine="polars",
    )

    assert isinstance(workload, RegisteredWorkload)
    assert workload.registry_key == "pytransformkit:customer360.plan"
    assert workload.integration_key == "pytransformkit"
    assert workload.engine == "polars"


def test_lot19_resource_reference_matches_pytransformkit_portable_shape() -> None:
    resource = PyTransformKitResourceReference(
        scheme="s3",
        locator="bucket/customer360/v1.parquet",
        media_type="application/vnd.apache.parquet",
        metadata=(("dataset", "customer360"),),
    )

    assert resource.as_portable_output() == {
        "kind": "pytransformkit.resource_reference",
        "scheme": "s3",
        "locator": "bucket/customer360/v1.parquet",
        "media_type": "application/vnd.apache.parquet",
        "metadata": {"dataset": "customer360"},
        "contract_version": "1",
    }


def test_lot19_planner_records_pytransformkit_requirement() -> None:
    transform = pytransformkit_v2_task(
        key="transform_customer_360",
        plan_ref="customer360.plan",
        engine="polars",
    )
    plan = WorkflowPlanner().compile(
        WorkflowDefinition(name="lot19-reference", tasks=(transform,))
    )

    assert plan.required_integrations == ("pytransformkit",)
    assert plan.task("transform_customer_360").required_integrations == ("pytransformkit",)


def test_lot19_snapshot_freezes_real_sibling_boundary() -> None:
    assert pytransformkit.v2_pytransformkit_integration_snapshot() == {
        "contract_version": "1",
        "integration_key": "pytransformkit",
        "registry_prefix": "pytransformkit:",
        "atomic_plan_boundary": True,
        "imports_pytransformkit": False,
        "workload_base": "RegisteredWorkload",
        "binding_contract": "V2WorkloadBinding",
        "portable_dependency_handoff": True,
        "resource_reference_shape": ("scheme", "locator", "media_type", "metadata"),
        "external_reference_contract": "ExternalRunRef",
        "workload_retry_owner": "pyworkflowkit",
        "provider_retry_owner": "pytransformkit",
        "unknown_outcome_requires_reconciliation": True,
        "raw_credentials_supported": False,
        "credential_reference_supported": True,
    }
