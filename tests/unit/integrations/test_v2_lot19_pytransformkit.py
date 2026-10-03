"""LOT-19 unit qualification for the canonical V2 PyTransformKit boundary."""

from __future__ import annotations

import pytest

from pyworkflowkit.authoring import RegisteredWorkload, TaskDefinition, WorkflowDefinition
from pyworkflowkit.diagnostics import (
    FailureCategory,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.integrations.pytransformkit import (
    V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION,
    PyTransformKitExecutionResult,
    PyTransformKitExecutionStatus,
    PyTransformKitResourceReference,
    PyTransformKitWorkload,
    PyTransformKitWorkloadHandler,
    pytransformkit_v2_task,
    pytransformkit_v2_workload_binding,
    v2_pytransformkit_integration_snapshot,
)
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.planning import WorkflowPlanner
from pyworkflowkit.policies import RetryPolicy
from pyworkflowkit.runtime import WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus


def _resource(locator: str = "bucket/customer360/v1.parquet") -> PyTransformKitResourceReference:
    return PyTransformKitResourceReference(
        scheme="s3",
        locator=locator,
        media_type="application/vnd.apache.parquet",
        metadata=(("format", "parquet"),),
    )


class _SuccessTransform:
    def __init__(self) -> None:
        self.inputs = None

    def run(self, *, context, inputs):
        self.inputs = inputs
        return PyTransformKitExecutionResult(
            transformation_execution_id=f"T-{context.attempt_id}",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
            resource=_resource(),
            engine_id="polars",
            plan_fingerprint="sha256:abc",
        )


class _KnownFailureTransform:
    def run(self, *, context, inputs):
        del context, inputs
        return PyTransformKitExecutionResult(
            transformation_execution_id="T-FAILED",
            status=PyTransformKitExecutionStatus.FAILED,
            engine_id="polars",
            error_code="PTK-EXEC-FAILED",
            provider_code="provider.failed",
            message_summary="transformation failed",
            retryable=False,
        )


class _RetryThenSuccessTransform:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, context, inputs):
        del inputs
        self.calls += 1
        if self.calls == 1:
            return PyTransformKitExecutionResult(
                transformation_execution_id=f"T-{context.attempt_id}",
                status=PyTransformKitExecutionStatus.FAILED,
                engine_id="polars",
                error_code="PTK-EXEC-TRANSIENT",
                message_summary="temporary provider failure",
                retryable=True,
            )
        return PyTransformKitExecutionResult(
            transformation_execution_id=f"T-{context.attempt_id}",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
            resource=_resource("bucket/customer360/v2.parquet"),
            engine_id="polars",
        )


class _UnknownTransform:
    def __init__(
        self,
        status: PyTransformKitExecutionStatus = PyTransformKitExecutionStatus.UNKNOWN_OUTCOME,
    ) -> None:
        self.status = status

    def run(self, *, context, inputs):
        del context, inputs
        return PyTransformKitExecutionResult(
            transformation_execution_id="T-UNKNOWN",
            status=self.status,
            engine_id="polars",
            status_locator="https://transform.invalid/executions/T-UNKNOWN",
            error_code="PTK-EXEC-UNKNOWN",
            message_summary="provider outcome requires reconciliation",
        )


class _ExplodingTransform:
    def run(self, *, context, inputs):
        del context, inputs
        raise RuntimeError("wrapper exploded")


class _InvalidTransformResult:
    def run(self, *, context, inputs):
        del context, inputs
        return object()


class _MustNotRunTransform:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, context, inputs):
        del context, inputs
        self.calls += 1
        raise AssertionError("must not execute")


def _run_transform_task(task, job, *, upstream=()):
    workload = task.workload
    assert isinstance(workload, PyTransformKitWorkload)
    binding = pytransformkit_v2_workload_binding(workload=workload, job=job)
    executor = InlineExecutor({binding.registry_key: binding.handler})
    metadata = InMemoryMetadataStore()
    result = WorkflowRuntime(executor=executor, metadata=metadata).run(
        WorkflowDefinition(name="lot19", version="1", tasks=(*upstream, task))
    )
    return result, metadata


def test_lot19_workload_is_portable_registered_workload_and_planner_integration() -> None:
    task = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        engine="polars",
        dependencies=("ingest_customers",),
        parameters=(("mode", "strict"),),
        credential_ref="secretref://transform/customer360",
    )
    ingest = TaskDefinition(
        key="ingest_customers",
        workload=lambda: {"kind": "dataset_version", "id": "customers-v1"},
    )

    workload = task.workload
    assert isinstance(workload, PyTransformKitWorkload)
    assert isinstance(workload, RegisteredWorkload)
    assert workload.registry_key == "pytransformkit:customer360.plan"
    assert workload.plan_ref == "customer360.plan"
    assert workload.engine == "polars"
    assert workload.credential_ref == "secretref://transform/customer360"
    assert task.portable is True

    plan = WorkflowPlanner().compile(
        WorkflowDefinition(name="lot19-plan", tasks=(ingest, task))
    )
    assert plan.required_integrations == ("pytransformkit",)
    assert plan.task("transform").required_integrations == ("pytransformkit",)
    assert plan.task("transform").executor_requirement.workload_kind == "registered"


def test_lot19_workload_fingerprint_contains_real_integration_semantics() -> None:
    workload = PyTransformKitWorkload(
        plan_ref="customer360.plan",
        engine="polars",
        parameters=(("mode", "strict"),),
        credential_ref="credential://transform",
    )

    payload = workload.fingerprint_payload()

    assert payload["integration_key"] == "pytransformkit"
    assert payload["plan_ref"] == "customer360.plan"
    assert payload["engine"] == "polars"
    assert payload["credential_ref"] == "credential://transform"


def test_lot19_resource_reference_matches_sibling_shape() -> None:
    reference = _resource()

    assert reference.as_portable_output() == {
        "kind": "pytransformkit.resource_reference",
        "scheme": "s3",
        "locator": "bucket/customer360/v1.parquet",
        "media_type": "application/vnd.apache.parquet",
        "metadata": {"format": "parquet"},
        "contract_version": "1",
    }


def test_lot19_reserved_parameters_cannot_be_overridden() -> None:
    for key in (
        "pytransformkit.plan_ref",
        "pytransformkit.engine",
        "pytransformkit.credential_ref",
    ):
        with pytest.raises(ValueError, match="reserved PyTransformKit"):
            PyTransformKitWorkload(
                plan_ref="customer360.plan",
                engine="polars",
                parameters=((key, "override"),),
            )


def test_lot19_pyworkflowkit_owns_workload_retry() -> None:
    job = _RetryThenSuccessTransform()
    task = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        engine="polars",
        retry_policy=RetryPolicy(max_attempts=2),
    )

    result, metadata = _run_transform_task(task, job)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert job.calls == 2
    assert result.task("transform").output["locator"].endswith("v2.parquet")
    task_run = metadata.list_task_runs(result.run_id)[0]
    assert len(metadata.list_task_attempts(task_run.task_run_id)) == 2


def test_lot19_success_receives_portable_inputs_and_persists_evidence() -> None:
    job = _SuccessTransform()
    ingest = TaskDefinition(
        key="ingest_customers",
        workload=lambda: {
            "kind": "pyingestkit.dataset_version_reference",
            "dataset_id": "customers",
            "version": "2026-10-03",
        },
    )
    transform = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        engine="polars",
        dependencies=("ingest_customers",),
        credential_ref="secretref://transform/customer360",
    )

    result, metadata = _run_transform_task(transform, job, upstream=(ingest,))

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert job.inputs == {
        "ingest_customers": {
            "kind": "pyingestkit.dataset_version_reference",
            "dataset_id": "customers",
            "version": "2026-10-03",
        }
    }
    output = result.task("transform").output
    assert output["scheme"] == "s3"
    assert output["locator"] == "bucket/customer360/v1.parquet"

    transform_run = next(
        item for item in metadata.list_task_runs(result.run_id) if item.task_key == "transform"
    )
    attempt = metadata.list_task_attempts(transform_run.task_run_id)[0]
    refs = metadata.list_external_run_refs(attempt.attempt_id)
    assert len(refs) == 1
    assert refs[0].provider == "pytransformkit"
    assert refs[0].kind == "transformation_execution"
    assert refs[0].external_run_id.startswith("T-")
    ref_metadata = dict(refs[0].metadata)
    assert ref_metadata["plan_ref"] == "customer360.plan"
    assert ref_metadata["engine"] == "polars"
    assert ref_metadata["plan_fingerprint"] == "sha256:abc"
    assert "credential_ref" not in ref_metadata

    checkpoint = metadata.get_task_output_checkpoint(transform_run.task_run_id)
    assert checkpoint.output["kind"] == "pytransformkit.resource_reference"


def test_lot19_confirmed_failure_is_known_provider_failure() -> None:
    task = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        engine="polars",
    )

    result, metadata = _run_transform_task(task, _KnownFailureTransform())

    assert result.status is WorkflowRunStatus.FAILED
    assert result.failure is not None
    assert result.failure.category is FailureCategory.EXTERNAL_PROVIDER
    assert result.failure.retryability is Retryability.NON_RETRYABLE
    assert result.failure.uncertainty is OutcomeUncertainty.KNOWN
    assert result.failure.external_run is not None
    assert result.failure.external_run.external_run_id == "T-FAILED"

    task_run = metadata.list_task_runs(result.run_id)[0]
    attempt = metadata.list_task_attempts(task_run.task_run_id)[0]
    assert metadata.list_external_run_refs(attempt.attempt_id)[0].provider == "pytransformkit"


@pytest.mark.parametrize(
    "status",
    [
        PyTransformKitExecutionStatus.UNKNOWN_OUTCOME,
        PyTransformKitExecutionStatus.REQUIRES_RECONCILIATION,
    ],
)
def test_lot19_uncertain_outcome_requires_reconciliation_without_blind_retry(
    status: PyTransformKitExecutionStatus,
) -> None:
    task = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        engine="polars",
        retry_policy=RetryPolicy(max_attempts=3),
    )

    result, metadata = _run_transform_task(task, _UnknownTransform(status))

    assert result.status is WorkflowRunStatus.UNKNOWN_OUTCOME
    assert result.failure is not None
    assert result.failure.category is FailureCategory.UNKNOWN_OUTCOME
    assert result.failure.retryability is Retryability.RETRYABLE_AFTER_RECONCILIATION
    assert result.failure.uncertainty is OutcomeUncertainty.REQUIRES_RECONCILIATION

    task_run = metadata.list_task_runs(result.run_id)[0]
    attempts = metadata.list_task_attempts(task_run.task_run_id)
    assert len(attempts) == 1
    assert metadata.list_external_run_refs(attempts[0].attempt_id)[0].external_run_id == "T-UNKNOWN"


def test_lot19_nonportable_dependency_fails_before_sibling_execution() -> None:
    job = _MustNotRunTransform()
    upstream = TaskDefinition(key="upstream", workload=lambda: object())
    transform = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        engine="polars",
        dependencies=("upstream",),
    )

    result, _ = _run_transform_task(transform, job, upstream=(upstream,))

    assert result.status is WorkflowRunStatus.FAILED
    assert result.failure is not None
    assert result.failure.error_code == "PWK-PYTRANSFORMKIT-NONPORTABLE-INPUT"
    assert result.failure.category is FailureCategory.CONTRACT_VIOLATION
    assert job.calls == 0


def test_lot19_wrapper_exception_and_invalid_result_fail_closed() -> None:
    task = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        engine="polars",
        retry_policy=RetryPolicy(max_attempts=3),
    )

    exploded, metadata = _run_transform_task(task, _ExplodingTransform())
    assert exploded.status is WorkflowRunStatus.FAILED
    assert exploded.failure is not None
    assert exploded.failure.error_code == "PWK-PYTRANSFORMKIT-WRAPPER-EXCEPTION"
    assert exploded.failure.retryability is Retryability.NON_RETRYABLE
    task_run = metadata.list_task_runs(exploded.run_id)[0]
    assert len(metadata.list_task_attempts(task_run.task_run_id)) == 1

    invalid, _ = _run_transform_task(task, _InvalidTransformResult())
    assert invalid.status is WorkflowRunStatus.FAILED
    assert invalid.failure is not None
    assert invalid.failure.error_code == "PWK-PYTRANSFORMKIT-RESULT-CONTRACT"


def test_lot19_terminal_statuses_preserve_timeout_and_cancellation_categories() -> None:
    class TerminalTransform:
        def __init__(self, status):
            self.status = status

        def run(self, *, context, inputs):
            del context, inputs
            return PyTransformKitExecutionResult(
                transformation_execution_id=f"T-{self.status.value}",
                status=self.status,
                error_code=f"PTK-{self.status.value}",
                retryable=self.status is PyTransformKitExecutionStatus.TIMED_OUT,
            )

    cancelled = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        engine="polars",
    )
    cancelled_result, _ = _run_transform_task(
        cancelled,
        TerminalTransform(PyTransformKitExecutionStatus.CANCELLED),
    )
    assert cancelled_result.failure is not None
    assert cancelled_result.failure.category is FailureCategory.CANCELLED

    timeout = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        engine="polars",
    )
    timed_out_result, _ = _run_transform_task(
        timeout,
        TerminalTransform(PyTransformKitExecutionStatus.TIMED_OUT),
    )
    assert timed_out_result.failure is not None
    assert timed_out_result.failure.category is FailureCategory.TIMEOUT
    assert timed_out_result.failure.retryability is Retryability.RETRYABLE


def test_lot19_result_and_resource_contract_versions_fail_closed() -> None:
    with pytest.raises(ValueError, match="resource contract version"):
        PyTransformKitResourceReference(
            scheme="s3",
            locator="bucket/x",
            contract_version="999",
        )

    with pytest.raises(ValueError, match="integration contract version"):
        PyTransformKitExecutionResult(
            transformation_execution_id="T-1",
            status=PyTransformKitExecutionStatus.FAILED,
            error_code="failed",
            contract_version="999",
        )


def test_lot19_result_validates_success_and_failure_shapes() -> None:
    with pytest.raises(ValueError, match="requires resource"):
        PyTransformKitExecutionResult(
            transformation_execution_id="T-1",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
        )
    with pytest.raises(ValueError, match="cannot define error fields"):
        PyTransformKitExecutionResult(
            transformation_execution_id="T-1",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
            resource=_resource(),
            error_code="unexpected",
        )
    with pytest.raises(ValueError, match="requires error_code"):
        PyTransformKitExecutionResult(
            transformation_execution_id="T-1",
            status=PyTransformKitExecutionStatus.FAILED,
        )


def test_lot19_binding_targets_exact_registered_workload_key() -> None:
    workload = PyTransformKitWorkload(
        plan_ref="customer360.plan",
        engine="polars",
    )
    binding = pytransformkit_v2_workload_binding(
        workload=workload,
        job=_SuccessTransform(),
    )

    assert binding.registry_key == workload.registry_key
    assert isinstance(binding.handler, PyTransformKitWorkloadHandler)


def test_lot19_snapshot_freezes_transform_boundary() -> None:
    snapshot = v2_pytransformkit_integration_snapshot()

    assert snapshot["contract_version"] == V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION
    assert snapshot["integration_key"] == "pytransformkit"
    assert snapshot["resource_reference_shape"] == (
        "scheme",
        "locator",
        "media_type",
        "metadata",
    )
    assert snapshot["workload_retry_owner"] == "pyworkflowkit"
    assert snapshot["provider_retry_owner"] == "pytransformkit"
    assert snapshot["unknown_outcome_requires_reconciliation"] is True
    assert snapshot["raw_credentials_supported"] is False
