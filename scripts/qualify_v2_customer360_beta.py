#!/usr/bin/env python3
"""Installed-artifact Customer 360 V2 beta qualification."""

from __future__ import annotations

import json

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.integrations.pyingestkit import (
    PyIngestKitExecutionResult,
    PyIngestKitExecutionStatus,
    PyIngestKitWorkload,
    pyingestkit_v2_task,
    pyingestkit_v2_workload_binding,
)
from pyworkflowkit.integrations.pytransformkit import (
    PyTransformKitExecutionResult,
    PyTransformKitExecutionStatus,
    PyTransformKitResourceReference,
    PyTransformKitWorkload,
    pytransformkit_v2_task,
    pytransformkit_v2_workload_binding,
)
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.policies import RetryPolicy
from pyworkflowkit.runtime import WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus


class IngestJob:
    def __init__(self, dataset_id: str) -> None:
        self.dataset_id = dataset_id

    def run(self, *, context):
        return PyIngestKitExecutionResult(
            external_run_id=f"I-{self.dataset_id}-{context.attempt_id}",
            status=PyIngestKitExecutionStatus.SUCCEEDED,
            output={
                "kind": "pyingestkit.dataset_version_reference",
                "dataset_id": self.dataset_id,
                "version": "beta",
            },
        )


class RetryTransformJob:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, context, inputs):
        self.calls += 1
        assert set(inputs) == {"ingest_customers", "ingest_orders"}
        if self.calls == 1:
            return PyTransformKitExecutionResult(
                transformation_execution_id=f"T-{context.attempt_id}",
                status=PyTransformKitExecutionStatus.FAILED,
                engine_id="polars",
                error_code="PTK-BETA-TRANSIENT",
                message_summary="beta transient transformation failure",
                retryable=True,
            )
        return PyTransformKitExecutionResult(
            transformation_execution_id=f"T-{context.attempt_id}",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
            engine_id="polars",
            plan_fingerprint="sha256:customer360-beta",
            resource=PyTransformKitResourceReference(
                scheme="s3",
                locator="warehouse/customer360/beta.parquet",
                media_type="application/vnd.apache.parquet",
                metadata=(("dataset", "customer360"),),
            ),
        )


class PublishJob:
    def run(self, *, context):
        resource = context.dependency_outputs["transform_customer_360"]
        return PyIngestKitExecutionResult(
            external_run_id=f"P-{context.attempt_id}",
            status=PyIngestKitExecutionStatus.SUCCEEDED,
            output={
                "kind": "pyingestkit.publication_reference",
                "locator": resource["locator"],
            },
        )


class MustNotRunTransform:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, context, inputs):
        del context, inputs
        self.calls += 1
        raise AssertionError("non-portable dependency must fail before sibling execution")


def _binding(task, job):
    workload = task.workload
    if isinstance(workload, PyIngestKitWorkload):
        return pyingestkit_v2_workload_binding(workload=workload, job=job)
    assert isinstance(workload, PyTransformKitWorkload)
    return pytransformkit_v2_workload_binding(workload=workload, job=job)


def _happy_path() -> dict[str, object]:
    customers = pyingestkit_v2_task(
        key="ingest_customers",
        job_ref="beta.customers",
    )
    orders = pyingestkit_v2_task(
        key="ingest_orders",
        job_ref="beta.orders",
    )
    transform = pytransformkit_v2_task(
        key="transform_customer_360",
        plan_ref="beta.customer360",
        engine="polars",
        dependencies=("ingest_customers", "ingest_orders"),
        retry_policy=RetryPolicy(max_attempts=2),
        credential_ref="secretref://beta/transform",
    )
    publish = pyingestkit_v2_task(
        key="publish_mart",
        job_ref="beta.publish",
        dependencies=("transform_customer_360",),
        credential_ref="secretref://beta/publish",
    )
    definition = WorkflowDefinition(
        name="customer360-beta",
        version="2.0.0b2",
        tasks=(customers, orders, transform, publish),
    )

    transform_job = RetryTransformJob()
    bindings = (
        _binding(customers, IngestJob("customers")),
        _binding(orders, IngestJob("orders")),
        _binding(transform, transform_job),
        _binding(publish, PublishJob()),
    )
    metadata = InMemoryMetadataStore()
    runtime = WorkflowRuntime(
        executor=InlineExecutor({item.registry_key: item.handler for item in bindings}),
        metadata=metadata,
    )

    result = runtime.run(definition)
    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert transform_job.calls == 2
    assert result.task("publish_mart").output["locator"] == ("warehouse/customer360/beta.parquet")

    lineage = runtime.lineage(definition, result.run_id)
    assert tuple(item.task_key for item in lineage.tasks) == (
        "ingest_customers",
        "ingest_orders",
        "transform_customer_360",
        "publish_mart",
    )
    assert len(lineage.dependencies) == 3

    by_key = {item.task_key: item for item in lineage.tasks}
    assert len(by_key["transform_customer_360"].attempt_ids) == 2
    assert len(by_key["transform_customer_360"].external_runs) == 2
    assert len(by_key["publish_mart"].external_runs) == 1
    assert all(item.output_digest is not None for item in lineage.tasks)

    all_refs = [ref for task in lineage.tasks for ref in task.external_runs]
    assert {ref.provider for ref in all_refs} == {"pyingestkit", "pytransformkit"}
    assert all("secretref://" not in repr(ref.metadata) for ref in all_refs)

    return {
        "workflow_status": result.status.value,
        "task_count": len(lineage.tasks),
        "dependency_count": len(lineage.dependencies),
        "transform_attempts": len(by_key["transform_customer_360"].attempt_ids),
        "external_run_count": len(all_refs),
    }


def _security_negative() -> dict[str, object]:
    job = MustNotRunTransform()
    upstream = TaskDefinition(key="unsafe", workload=lambda: object())
    transform = pytransformkit_v2_task(
        key="transform",
        plan_ref="beta.security",
        engine="polars",
        dependencies=("unsafe",),
    )
    workload = transform.workload
    assert isinstance(workload, PyTransformKitWorkload)
    binding = pytransformkit_v2_workload_binding(workload=workload, job=job)

    result = WorkflowRuntime(
        executor=InlineExecutor({binding.registry_key: binding.handler}),
        metadata=InMemoryMetadataStore(),
    ).run(
        WorkflowDefinition(
            name="customer360-beta-security",
            tasks=(upstream, transform),
        )
    )

    assert result.status is WorkflowRunStatus.FAILED
    assert result.failure is not None
    assert result.failure.error_code == "PWK-PYTRANSFORMKIT-NONPORTABLE-INPUT"
    assert job.calls == 0

    return {
        "workflow_status": result.status.value,
        "error_code": result.failure.error_code,
        "sibling_calls": job.calls,
    }



def _incompatible_contracts() -> dict[str, bool]:
    checks: dict[str, bool] = {}

    for name, factory in (
        (
            "pyingestkit_workload",
            lambda: PyIngestKitWorkload(
                job_ref="beta.incompatible",
                contract_version="999",
            ),
        ),
        (
            "pytransformkit_workload",
            lambda: PyTransformKitWorkload(
                plan_ref="beta.incompatible",
                engine="polars",
                contract_version="999",
            ),
        ),
        (
            "pyingestkit_result",
            lambda: PyIngestKitExecutionResult(
                external_run_id="I-INCOMPATIBLE",
                status=PyIngestKitExecutionStatus.FAILED,
                error_code="PIK-INCOMPATIBLE",
                contract_version="999",
            ),
        ),
        (
            "pytransformkit_result",
            lambda: PyTransformKitExecutionResult(
                transformation_execution_id="T-INCOMPATIBLE",
                status=PyTransformKitExecutionStatus.FAILED,
                error_code="PTK-INCOMPATIBLE",
                contract_version="999",
            ),
        ),
    ):
        try:
            factory()
        except ValueError:
            checks[name] = True
        else:
            checks[name] = False

    assert all(checks.values())
    return checks

def main() -> None:
    payload = {
        "contract": "pyworkflowkit.customer360_beta",
        "contract_version": "1",
        "happy_path": _happy_path(),
        "security_negative": _security_negative(),
        "incompatible_contracts": _incompatible_contracts(),
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
