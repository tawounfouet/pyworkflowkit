"""LOT-19 Customer 360 cross-framework acceptance scenario."""

from __future__ import annotations

from pyworkflowkit.authoring import WorkflowDefinition
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
from pyworkflowkit.planning import WorkflowPlanner
from pyworkflowkit.runtime import WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus


class DatasetIngestion:
    def __init__(self, dataset_id: str) -> None:
        self.dataset_id = dataset_id

    def run(self, *, context):
        return PyIngestKitExecutionResult(
            external_run_id=f"ingest-{self.dataset_id}-{context.attempt_id}",
            status=PyIngestKitExecutionStatus.SUCCEEDED,
            output={
                "kind": "pyingestkit.dataset_version_reference",
                "dataset_id": self.dataset_id,
                "version": "2026-10-03",
            },
        )


class Customer360Transform:
    def run(self, *, context, inputs):
        assert set(inputs) == {"ingest_customers", "ingest_orders"}
        return PyTransformKitExecutionResult(
            transformation_execution_id=f"T-{context.attempt_id}",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
            engine_id="polars",
            plan_fingerprint="sha256:customer360",
            resource=PyTransformKitResourceReference(
                scheme="s3",
                locator="warehouse/customer360/v1.parquet",
                media_type="application/vnd.apache.parquet",
                metadata=(("dataset", "customer360"),),
            ),
        )


class MartPublication:
    def run(self, *, context):
        resource = context.dependency_outputs["transform_customer_360"]
        assert isinstance(resource, dict)
        assert resource["kind"] == "pytransformkit.resource_reference"
        return PyIngestKitExecutionResult(
            external_run_id=f"publish-{context.attempt_id}",
            status=PyIngestKitExecutionStatus.SUCCEEDED,
            output={
                "kind": "pyingestkit.publication_reference",
                "locator": resource["locator"],
            },
        )


def binding(task, job):
    workload = task.workload
    if isinstance(workload, PyIngestKitWorkload):
        return pyingestkit_v2_workload_binding(workload=workload, job=job)
    assert isinstance(workload, PyTransformKitWorkload)
    return pytransformkit_v2_workload_binding(workload=workload, job=job)


def test_lot19_customer360_cross_framework_happy_path() -> None:
    customers = pyingestkit_v2_task(
        key="ingest_customers",
        job_ref="customer360.customers",
    )
    orders = pyingestkit_v2_task(
        key="ingest_orders",
        job_ref="customer360.orders",
    )
    transform = pytransformkit_v2_task(
        key="transform_customer_360",
        plan_ref="customer360.join",
        engine="polars",
        dependencies=("ingest_customers", "ingest_orders"),
    )
    publish = pyingestkit_v2_task(
        key="publish_mart",
        job_ref="customer360.publish",
        dependencies=("transform_customer_360",),
    )

    bindings = (
        binding(customers, DatasetIngestion("customers")),
        binding(orders, DatasetIngestion("orders")),
        binding(transform, Customer360Transform()),
        binding(publish, MartPublication()),
    )
    executor = InlineExecutor({item.registry_key: item.handler for item in bindings})
    metadata = InMemoryMetadataStore()
    definition = WorkflowDefinition(
        name="customer360",
        version="2",
        tasks=(customers, orders, transform, publish),
    )

    plan = WorkflowPlanner().compile(definition)
    assert plan.groups == (
        ("ingest_customers", "ingest_orders"),
        ("transform_customer_360",),
        ("publish_mart",),
    )
    assert plan.required_integrations == ("pyingestkit", "pytransformkit")

    result = WorkflowRuntime(executor=executor, metadata=metadata).run(definition)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert result.task("ingest_customers").output["dataset_id"] == "customers"
    assert result.task("ingest_orders").output["dataset_id"] == "orders"
    assert result.task("transform_customer_360").output["scheme"] == "s3"
    assert (
        result.task("transform_customer_360").output["locator"]
        == "warehouse/customer360/v1.parquet"
    )
    assert result.task("publish_mart").output["locator"] == "warehouse/customer360/v1.parquet"

    providers = {}
    for task_run in metadata.list_task_runs(result.run_id):
        attempt = metadata.list_task_attempts(task_run.task_run_id)[0]
        refs = metadata.list_external_run_refs(attempt.attempt_id)
        assert len(refs) == 1
        providers[task_run.task_key] = refs[0].provider

    assert providers == {
        "ingest_customers": "pyingestkit",
        "ingest_orders": "pyingestkit",
        "transform_customer_360": "pytransformkit",
        "publish_mart": "pyingestkit",
    }


def test_lot19_transform_handoff_is_durable_portable_checkpoint() -> None:
    ingest = pyingestkit_v2_task(
        key="ingest_customers",
        job_ref="customer360.customers",
    )
    transform = pytransformkit_v2_task(
        key="transform_customer_360",
        plan_ref="customer360.project",
        engine="polars",
        dependencies=("ingest_customers",),
    )

    class SingleTransform:
        def run(self, *, context, inputs):
            assert inputs["ingest_customers"]["dataset_id"] == "customers"
            return PyTransformKitExecutionResult(
                transformation_execution_id=f"T-{context.attempt_id}",
                status=PyTransformKitExecutionStatus.SUCCEEDED,
                engine_id="polars",
                resource=PyTransformKitResourceReference(
                    scheme="file",
                    locator="customer360/single.parquet",
                    media_type="application/vnd.apache.parquet",
                ),
            )

    bindings = (
        binding(ingest, DatasetIngestion("customers")),
        binding(transform, SingleTransform()),
    )
    metadata = InMemoryMetadataStore()
    result = WorkflowRuntime(
        executor=InlineExecutor({item.registry_key: item.handler for item in bindings}),
        metadata=metadata,
    ).run(WorkflowDefinition(name="customer360-portable", tasks=(ingest, transform)))

    assert result.status is WorkflowRunStatus.SUCCEEDED
    task_runs = {item.task_key: item for item in metadata.list_task_runs(result.run_id)}
    ingest_checkpoint = metadata.get_task_output_checkpoint(
        task_runs["ingest_customers"].task_run_id
    )
    transform_checkpoint = metadata.get_task_output_checkpoint(
        task_runs["transform_customer_360"].task_run_id
    )
    assert ingest_checkpoint.output["kind"] == "pyingestkit.dataset_version_reference"
    assert transform_checkpoint.output["kind"] == "pytransformkit.resource_reference"
    assert transform_checkpoint.output["scheme"] == "file"
