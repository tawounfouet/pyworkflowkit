"""LOT-20 cross-framework retry, uncertainty and recovery conformance."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

from pyworkflowkit.authoring import WorkflowDefinition
from pyworkflowkit.errors import PyIngestKitRetryOwnershipError
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.integrations.pyingestkit import (
    PyIngestKitExecutionResult,
    PyIngestKitExecutionStatus,
    PyIngestKitRetryOwner,
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
from pyworkflowkit.persistence import InMemoryMetadataStore, SQLiteMetadataStore
from pyworkflowkit.policies import RetryPolicy
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    ExternalRunRef,
    ExternalRunStatus,
    ExternalRunVerifierRegistry,
    ReconciliationDisposition,
    ReconciliationService,
    WorkflowRuntime,
)
from pyworkflowkit.states import TaskAttemptStatus, TaskRunStatus, WorkflowRunStatus


class DatasetIngestion:
    def __init__(self, dataset_id: str) -> None:
        self.dataset_id = dataset_id
        self.calls = 0

    def run(self, *, context):
        self.calls += 1
        return PyIngestKitExecutionResult(
            external_run_id=f"INGEST-{self.dataset_id}-{context.attempt_id}",
            status=PyIngestKitExecutionStatus.SUCCEEDED,
            output={
                "kind": "pyingestkit.dataset_version_reference",
                "dataset_id": self.dataset_id,
                "version": "2026-10-03",
            },
            metadata=(("phase", "ingest"),),
        )


class SuccessfulTransform:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, context, inputs):
        self.calls += 1
        assert set(inputs) == {"ingest_customers", "ingest_orders"}
        return PyTransformKitExecutionResult(
            transformation_execution_id=f"T-{context.attempt_id}",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
            engine_id="polars",
            plan_fingerprint="sha256:lot20-customer360",
            resource=PyTransformKitResourceReference(
                scheme="s3",
                locator="warehouse/customer360/v1.parquet",
                media_type="application/vnd.apache.parquet",
                metadata=(("dataset", "customer360"),),
            ),
        )


class UnknownTransform:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, context, inputs):
        self.calls += 1
        assert inputs["ingest_customers"]["dataset_id"] == "customers"
        return PyTransformKitExecutionResult(
            transformation_execution_id=f"T-UNKNOWN-{context.attempt_id}",
            status=PyTransformKitExecutionStatus.UNKNOWN_OUTCOME,
            engine_id="polars",
            status_locator="https://transform.invalid/executions/current",
            error_code="PTK-EXEC-UNKNOWN",
            message_summary="transformation acknowledgement is ambiguous",
        )


class RetryThenSuccessTransform:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, context, inputs):
        del inputs
        self.calls += 1
        metadata = (("provider_retry_count", "2"),)
        if self.calls == 1:
            return PyTransformKitExecutionResult(
                transformation_execution_id=f"T-{context.attempt_id}",
                status=PyTransformKitExecutionStatus.FAILED,
                engine_id="polars",
                metadata=metadata,
                error_code="PTK-EXEC-TRANSIENT",
                message_summary="provider retry scope exhausted for this execution",
                retryable=True,
            )
        return PyTransformKitExecutionResult(
            transformation_execution_id=f"T-{context.attempt_id}",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
            engine_id="polars",
            metadata=metadata,
            resource=PyTransformKitResourceReference(
                scheme="memory",
                locator="customer360/retried",
            ),
        )


class UnknownPublication:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, context):
        self.calls += 1
        resource = context.dependency_outputs["transform_customer_360"]
        assert resource["kind"] == "pytransformkit.resource_reference"
        return PyIngestKitExecutionResult(
            external_run_id=f"PUBLISH-UNKNOWN-{context.attempt_id}",
            status=PyIngestKitExecutionStatus.UNKNOWN_OUTCOME,
            status_locator="https://ingest.invalid/publications/current",
            error_code="PIK-PUBLISH-UNKNOWN",
            message_summary="publication acknowledgement was lost",
        )


class SuccessfulPublication:
    def run(self, *, context):
        resource = context.dependency_outputs["transform_customer_360"]
        return PyIngestKitExecutionResult(
            external_run_id=f"PUBLISH-{context.attempt_id}",
            status=PyIngestKitExecutionStatus.SUCCEEDED,
            output={
                "kind": "pyingestkit.publication_reference",
                "locator": resource["locator"],
            },
        )


@dataclass
class StaticVerifier:
    provider: str
    status: ExternalRunStatus
    expected_external_run_id: str | None = None

    def verify(self, external_ref: ExternalRunRef) -> ExternalRunStatus:
        if self.expected_external_run_id is not None:
            assert external_ref.external_run_id == self.expected_external_run_id
        return self.status


def _binding(task, job):
    workload = task.workload
    if isinstance(workload, PyIngestKitWorkload):
        return pyingestkit_v2_workload_binding(workload=workload, job=job)
    assert isinstance(workload, PyTransformKitWorkload)
    return pytransformkit_v2_workload_binding(workload=workload, job=job)


def _executor_for(definition: WorkflowDefinition, jobs: tuple[object, ...]) -> InlineExecutor:
    bindings = tuple(_binding(task, job) for task, job in zip(definition.tasks, jobs, strict=True))
    return InlineExecutor({item.registry_key: item.handler for item in bindings})


def test_lot20_equivalent_retry_scopes_cannot_be_stacked_implicitly() -> None:
    with pytest.raises(PyIngestKitRetryOwnershipError):
        pyingestkit_v2_task(
            key="ingest",
            job_ref="lot20.ingest",
            retry_owner=PyIngestKitRetryOwner.PYINGESTKIT,
            retry_policy=RetryPolicy(max_attempts=2),
        )

    job = RetryThenSuccessTransform()
    transform = pytransformkit_v2_task(
        key="transform",
        plan_ref="lot20.retry",
        engine="polars",
        retry_policy=RetryPolicy(max_attempts=2),
    )
    workload = transform.workload
    assert isinstance(workload, PyTransformKitWorkload)
    binding = pytransformkit_v2_workload_binding(workload=workload, job=job)
    metadata = InMemoryMetadataStore()

    result = WorkflowRuntime(
        executor=InlineExecutor({binding.registry_key: binding.handler}),
        metadata=metadata,
    ).run(WorkflowDefinition(name="lot20-retry", tasks=(transform,)))

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert job.calls == 2

    task_run = metadata.list_task_runs(result.run_id)[0]
    attempts = metadata.list_task_attempts(task_run.task_run_id)
    assert len(attempts) == 2

    refs = [metadata.list_external_run_refs(attempt.attempt_id)[0] for attempt in attempts]
    assert len({ref.external_run_id for ref in refs}) == 2
    assert all(dict(ref.metadata)["provider_retry_count"] == "2" for ref in refs)


def test_lot20_transform_unknown_outcome_survives_sqlite_restart_and_reconciles_same_attempt(
    tmp_path: Path,
) -> None:
    database = tmp_path / "lot20-transform-recovery.sqlite3"
    customers_job = DatasetIngestion("customers")
    customers = pyingestkit_v2_task(
        key="ingest_customers",
        job_ref="lot20.customers",
    )
    transform_job = UnknownTransform()
    transform = pytransformkit_v2_task(
        key="transform_customer_360",
        plan_ref="lot20.customer360",
        engine="polars",
        dependencies=("ingest_customers",),
        retry_policy=RetryPolicy(max_attempts=3),
    )
    definition = WorkflowDefinition(
        name="lot20-transform-recovery",
        tasks=(customers, transform),
    )
    bindings = (
        _binding(customers, customers_job),
        _binding(transform, transform_job),
    )

    with SQLiteMetadataStore(database, wal=False) as store:
        result = WorkflowRuntime(
            executor=InlineExecutor({item.registry_key: item.handler for item in bindings}),
            metadata=store,
        ).run(definition)

        assert result.status is WorkflowRunStatus.UNKNOWN_OUTCOME
        task_runs = {item.task_key: item for item in store.list_task_runs(result.run_id)}
        transform_run = task_runs["transform_customer_360"]
        attempts = store.list_task_attempts(transform_run.task_run_id)
        assert len(attempts) == 1
        original_attempt_id = attempts[0].attempt_id
        refs = store.list_external_run_refs(original_attempt_id)
        assert len(refs) == 1
        external_id = refs[0].external_run_id

        ingest_checkpoint = store.get_task_output_checkpoint(
            task_runs["ingest_customers"].task_run_id
        )
        assert ingest_checkpoint.output["dataset_id"] == "customers"

    registry = ExternalRunVerifierRegistry()
    registry.register(
        StaticVerifier(
            provider="pytransformkit",
            status=ExternalRunStatus.SUCCEEDED,
            expected_external_run_id=external_id,
        )
    )

    with SQLiteMetadataStore(database, wal=False) as reopened:
        report = ReconciliationService(
            metadata=reopened,
            verifier_registry=registry,
        ).reconcile(result.run_id)

        assert report.fully_resolved is True
        assert report.workflow_status_before is WorkflowRunStatus.UNKNOWN_OUTCOME
        assert report.workflow_status_after is WorkflowRunStatus.SUCCEEDED
        reconciliation = report.task_reconciliations[0]
        assert reconciliation.disposition is ReconciliationDisposition.RESOLVED_SUCCEEDED
        assert reconciliation.attempt_id == original_attempt_id

        transform_run = next(
            item
            for item in reopened.list_task_runs(result.run_id)
            if item.task_key == "transform_customer_360"
        )
        attempts = reopened.list_task_attempts(transform_run.task_run_id)
        assert len(attempts) == 1
        assert attempts[0].attempt_id == original_attempt_id
        assert attempts[0].status is TaskAttemptStatus.SUCCEEDED
        assert transform_run.status is TaskRunStatus.SUCCEEDED
        persisted_ref = reopened.list_external_run_refs(original_attempt_id)[0]
        assert persisted_ref.external_run_id == external_id

    assert transform_job.calls == 1


def test_lot20_publication_uncertainty_reconciles_after_restart_without_republishing(
    tmp_path: Path,
) -> None:
    database = tmp_path / "lot20-publication-recovery.sqlite3"
    customers_job = DatasetIngestion("customers")
    orders_job = DatasetIngestion("orders")
    transform_job = SuccessfulTransform()
    publication_job = UnknownPublication()

    customers = pyingestkit_v2_task(
        key="ingest_customers",
        job_ref="lot20.customers",
    )
    orders = pyingestkit_v2_task(
        key="ingest_orders",
        job_ref="lot20.orders",
    )
    transform = pytransformkit_v2_task(
        key="transform_customer_360",
        plan_ref="lot20.customer360",
        engine="polars",
        dependencies=("ingest_customers", "ingest_orders"),
    )
    publish = pyingestkit_v2_task(
        key="publish_mart",
        job_ref="lot20.publish",
        dependencies=("transform_customer_360",),
        retry_owner=PyIngestKitRetryOwner.PYWORKFLOWKIT,
        retry_policy=RetryPolicy(max_attempts=3),
    )
    definition = WorkflowDefinition(
        name="lot20-publication-recovery",
        tasks=(customers, orders, transform, publish),
    )
    jobs = (customers_job, orders_job, transform_job, publication_job)

    correlation = CorrelationContext(
        correlation_id=CorrelationId.parse("C-LOT20"),
        causation_id="request-42",
    )

    with SQLiteMetadataStore(database, wal=False) as store:
        result = WorkflowRuntime(
            executor=_executor_for(definition, jobs),
            metadata=store,
        ).run(definition, correlation=correlation)

        assert result.status is WorkflowRunStatus.UNKNOWN_OUTCOME
        task_runs = {item.task_key: item for item in store.list_task_runs(result.run_id)}
        publish_run = task_runs["publish_mart"]
        publish_attempts = store.list_task_attempts(publish_run.task_run_id)
        assert len(publish_attempts) == 1
        publish_attempt_id = publish_attempts[0].attempt_id

        refs_by_task = {}
        for task_key, task_run in task_runs.items():
            attempts = store.list_task_attempts(task_run.task_run_id)
            assert len(attempts) == 1
            refs = store.list_external_run_refs(attempts[0].attempt_id)
            assert len(refs) == 1
            refs_by_task[task_key] = refs[0]

        assert {ref.provider for ref in refs_by_task.values()} == {
            "pyingestkit",
            "pytransformkit",
        }
        assert all(str(ref.correlation_id) == "C-LOT20" for ref in refs_by_task.values())
        assert all(ref.causation_id == "request-42" for ref in refs_by_task.values())

        transform_checkpoint = store.get_task_output_checkpoint(
            task_runs["transform_customer_360"].task_run_id
        )
        assert transform_checkpoint.output["kind"] == "pytransformkit.resource_reference"
        assert transform_checkpoint.output["locator"] == "warehouse/customer360/v1.parquet"

        publish_ref = refs_by_task["publish_mart"]
        assert publish_ref.status_hint == "unknown_outcome"
        publish_external_id = publish_ref.external_run_id

    registry = ExternalRunVerifierRegistry()
    registry.register(
        StaticVerifier(
            provider="pyingestkit",
            status=ExternalRunStatus.SUCCEEDED,
            expected_external_run_id=publish_external_id,
        )
    )

    with SQLiteMetadataStore(database, wal=False) as reopened:
        report = ReconciliationService(
            metadata=reopened,
            verifier_registry=registry,
        ).reconcile(result.run_id)

        assert report.fully_resolved is True
        assert report.workflow_status_after is WorkflowRunStatus.SUCCEEDED
        publish_run = next(
            item
            for item in reopened.list_task_runs(result.run_id)
            if item.task_key == "publish_mart"
        )
        attempts = reopened.list_task_attempts(publish_run.task_run_id)
        assert len(attempts) == 1
        assert attempts[0].attempt_id == publish_attempt_id
        assert attempts[0].status is TaskAttemptStatus.SUCCEEDED

    assert publication_job.calls == 1
    assert transform_job.calls == 1
    assert customers_job.calls == 1
    assert orders_job.calls == 1


def test_lot20_cancelled_provider_truth_resolves_ambiguous_attempt_without_duplicate_execution(
    tmp_path: Path,
) -> None:
    database = tmp_path / "lot20-cancelled-recovery.sqlite3"
    transform_job = UnknownTransform()
    upstream_job = DatasetIngestion("customers")

    upstream = pyingestkit_v2_task(
        key="ingest_customers",
        job_ref="lot20.customers",
    )
    transform = pytransformkit_v2_task(
        key="transform_customer_360",
        plan_ref="lot20.customer360",
        engine="polars",
        dependencies=("ingest_customers",),
    )
    definition = WorkflowDefinition(
        name="lot20-cancel-reconcile",
        tasks=(upstream, transform),
    )
    bindings = (
        _binding(upstream, upstream_job),
        _binding(transform, transform_job),
    )

    with SQLiteMetadataStore(database, wal=False) as store:
        result = WorkflowRuntime(
            executor=InlineExecutor({item.registry_key: item.handler for item in bindings}),
            metadata=store,
        ).run(definition)
        transform_run = next(
            item
            for item in store.list_task_runs(result.run_id)
            if item.task_key == "transform_customer_360"
        )
        attempt = store.list_task_attempts(transform_run.task_run_id)[0]
        external_id = store.list_external_run_refs(attempt.attempt_id)[0].external_run_id
        attempt_id = attempt.attempt_id

    registry = ExternalRunVerifierRegistry()
    registry.register(
        StaticVerifier(
            provider="pytransformkit",
            status=ExternalRunStatus.CANCELLED,
            expected_external_run_id=external_id,
        )
    )

    with SQLiteMetadataStore(database, wal=False) as reopened:
        report = ReconciliationService(
            metadata=reopened,
            verifier_registry=registry,
        ).reconcile(result.run_id)

        assert report.workflow_status_after is WorkflowRunStatus.CANCELLED
        assert report.task_reconciliations[0].disposition is (
            ReconciliationDisposition.RESOLVED_CANCELLED
        )
        transform_run = next(
            item
            for item in reopened.list_task_runs(result.run_id)
            if item.task_key == "transform_customer_360"
        )
        attempts = reopened.list_task_attempts(transform_run.task_run_id)
        assert len(attempts) == 1
        assert attempts[0].attempt_id == attempt_id
        assert attempts[0].status is TaskAttemptStatus.CANCELLED
        assert transform_run.status is TaskRunStatus.CANCELLED

    assert transform_job.calls == 1


def test_lot20_core_and_v2_boundaries_import_without_sibling_packages() -> None:
    code = textwrap.dedent(
        """
        import builtins

        real_import = builtins.__import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "pyingestkit" or name.startswith("pyingestkit."):
                raise AssertionError("PyIngestKit import leaked into PyWorkflowKit")
            if name == "pytransformkit" or name.startswith("pytransformkit."):
                raise AssertionError("PyTransformKit import leaked into PyWorkflowKit")
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = guarded_import

        import pyworkflowkit
        import pyworkflowkit.integrations.pyingestkit
        import pyworkflowkit.integrations.pytransformkit

        assert pyworkflowkit.__version__
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
