"""LOT-18 reference acceptance for canonical V2 PyIngestKit integration."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.integrations.pyingestkit as pyingestkit
from pyworkflowkit.authoring import RegisteredWorkload, WorkflowDefinition
from pyworkflowkit.integrations.pyingestkit import (
    PyIngestKitRetryOwner,
    PyIngestKitWorkload,
    pyingestkit_v2_task,
)
from pyworkflowkit.planning import WorkflowPlanner


def test_lot18_qualified_surface_is_additive_to_legacy_adapter() -> None:
    legacy = {
        "PyIngestKitJob",
        "PyIngestKitRunResult",
        "PyIngestKitTaskAdapter",
        "pyingestkit_task",
    }
    v2 = {
        "PyIngestKitExecutionJob",
        "PyIngestKitExecutionResult",
        "PyIngestKitExecutionStatus",
        "PyIngestKitWorkload",
        "PyIngestKitWorkloadHandler",
        "pyingestkit_v2_task",
        "pyingestkit_v2_workload_binding",
        "v2_pyingestkit_integration_snapshot",
    }

    assert legacy.issubset(set(pyingestkit.__all__))
    assert v2.issubset(set(pyingestkit.__all__))
    for name in v2:
        assert name not in pyworkflowkit.__all__


def test_lot18_descriptor_uses_registered_workload_runtime_path() -> None:
    workload = PyIngestKitWorkload(
        job_ref="customer360.customers",
        retry_owner=PyIngestKitRetryOwner.PYINGESTKIT,
    )

    assert isinstance(workload, RegisteredWorkload)
    assert workload.registry_key == "pyingestkit:customer360.customers"
    assert workload.integration_key == "pyingestkit"


def test_lot18_customer360_ingestion_tasks_compile_as_atomic_sibling_jobs() -> None:
    customers = pyingestkit_v2_task(
        key="ingest_customers",
        job_ref="customer360.customers",
    )
    orders = pyingestkit_v2_task(
        key="ingest_orders",
        job_ref="customer360.orders",
    )

    plan = WorkflowPlanner().compile(
        WorkflowDefinition(
            name="customer360-lot18",
            tasks=(customers, orders),
        )
    )

    assert plan.topological_order == ("ingest_customers", "ingest_orders")
    assert plan.required_integrations == ("pyingestkit",)
    assert all(entry.portable for entry in plan.tasks)
    assert all(entry.executor_requirement.workload_kind == "registered" for entry in plan.tasks)


def test_lot18_contract_snapshot_is_fail_closed_and_dependency_free() -> None:
    snapshot = pyingestkit.v2_pyingestkit_integration_snapshot()

    assert snapshot == {
        "contract_version": "1",
        "integration_key": "pyingestkit",
        "registry_prefix": "pyingestkit:",
        "atomic_job_boundary": True,
        "imports_pyingestkit": False,
        "workload_base": "RegisteredWorkload",
        "binding_contract": "V2WorkloadBinding",
        "success_contract": "TaskExecutionResult",
        "failure_contract": "FailureEvidence",
        "external_reference_contract": "ExternalRunRef",
        "unknown_outcome_requires_reconciliation": True,
        "raw_credentials_supported": False,
        "credential_reference_supported": True,
        "implicit_retry_multiplication": False,
    }
