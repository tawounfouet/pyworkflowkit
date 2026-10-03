"""LOT-19 qualification for the canonical V2 PyTransformKit boundary."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pyworkflowkit.authoring import RegisteredWorkload, TaskDefinition, WorkflowDefinition
from pyworkflowkit.diagnostics import (
    FailureCategory,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.errors import PyTransformKitRetryOwnershipError
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.integrations.pytransformkit import (
    V2_PYTRANSFORMKIT_INTEGRATION_CONTRACT_VERSION,
    PyTransformKitExecutionResult,
    PyTransformKitExecutionStatus,
    PyTransformKitResourceReference,
    PyTransformKitRetryOwner,
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


class _SuccessTransform:
    def __init__(self) -> None:
        self.inputs: Mapping[str, object] | None = None

    def run(self, *, context, inputs):
        self.inputs = inputs
        return PyTransformKitExecutionResult(
            external_run_id=f"transform-{context.attempt_id}",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
            resource=PyTransformKitResourceReference(
                resource_id="customer360-v1",
                uri="resource://customer360/v1",
                version="1",
                metadata=(("model", "customer360"),),
            ),
            metadata=(("engine", "polars"),),
        )


class _KnownFailureTransform:
    def run(self, *, context, inputs):
        del context, inputs
        return PyTransformKitExecutionResult(
            external_run_id="TRANSFORM-FAILED",
            status=PyTransformKitExecutionStatus.FAILED,
            error_code="TRANSFORM-500",
            provider_code="500",
            message_summary="transformation failed",
            retryable=False,
        )


class _UnknownTransform:
    def run(self, *, context, inputs):
        del context, inputs
        return PyTransformKitExecutionResult(
            external_run_id="TRANSFORM-UNKNOWN",
            status=PyTransformKitExecutionStatus.UNKNOWN_OUTCOME,
            status_locator="https://transform.invalid/runs/TRANSFORM-UNKNOWN",
            error_code="TRANSFORM-UNKNOWN",
            message_summary="transformation outcome is unknown",
        )


class _RetryThenSuccessTransform:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, context, inputs):
        del inputs
        self.calls += 1
        if self.calls == 1:
            return PyTransformKitExecutionResult(
                external_run_id=f"transform-{context.attempt_id}",
                status=PyTransformKitExecutionStatus.FAILED,
                error_code="TRANSFORM-TRANSIENT",
                message_summary="temporary transformation failure",
                retryable=True,
            )
        return PyTransformKitExecutionResult(
            external_run_id=f"transform-{context.attempt_id}",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
            resource=PyTransformKitResourceReference(
                resource_id="customer360-v2",
                uri="resource://customer360/v2",
            ),
        )


class _ExplodingTransform:
    def run(self, *, context, inputs):
        del context, inputs
        raise RuntimeError("transform wrapper exploded")


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
        raise AssertionError("non-portable inputs must be rejected before sibling execution")


def _run_transform_task(
    task: TaskDefinition,
    job: object,
    *,
    upstream: tuple[TaskDefinition, ...] = (),
):
    workload = task.workload
    assert isinstance(workload, PyTransformKitWorkload)
    binding = pytransformkit_v2_workload_binding(
        workload=workload,
        job=job,  # type: ignore[arg-type]
    )
    executor = InlineExecutor({binding.registry_key: binding.handler})
    metadata = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=executor, metadata=metadata)
    result = runtime.run(
        WorkflowDefinition(
            name="lot19",
            version="1",
            tasks=(*upstream, task),
        )
    )
    return result, metadata


def test_lot19_workload_is_portable_registered_workload_and_planner_integration() -> None:
    task = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
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
    assert workload.retry_owner is PyTransformKitRetryOwner.PYTRANSFORMKIT
    assert workload.credential_ref == "secretref://transform/customer360"
    assert task.portable is True

    plan = WorkflowPlanner().compile(WorkflowDefinition(name="lot19-plan", tasks=(ingest, task)))
    assert plan.required_integrations == ("pytransformkit",)
    assert plan.task("transform").required_integrations == ("pytransformkit",)
    assert plan.task("transform").executor_requirement.workload_kind == "registered"


def test_lot19_workload_fingerprint_contains_integration_semantics() -> None:
    workload = PyTransformKitWorkload(
        plan_ref="customer360.plan",
        parameters=(("engine", "polars"),),
        retry_owner=PyTransformKitRetryOwner.PYWORKFLOWKIT,
        credential_ref="credential://transform",
    )

    payload = workload.fingerprint_payload()

    assert payload["integration_key"] == "pytransformkit"
    assert payload["plan_ref"] == "customer360.plan"
    assert payload["retry_owner"] == "pyworkflowkit"
    assert payload["credential_ref"] == "credential://transform"


def test_lot19_resource_reference_is_strictly_portable() -> None:
    reference = PyTransformKitResourceReference(
        resource_id="mart-v1",
        uri="s3://bucket/mart/v1",
        version="1",
        metadata=(("format", "parquet"),),
    )

    assert reference.as_portable_output() == {
        "kind": "pytransformkit.resource_reference",
        "resource_id": "mart-v1",
        "uri": "s3://bucket/mart/v1",
        "version": "1",
        "metadata": {"format": "parquet"},
        "contract_version": "1",
    }


def test_lot19_reserved_parameters_cannot_be_overridden() -> None:
    with pytest.raises(ValueError, match="reserved PyTransformKit"):
        PyTransformKitWorkload(
            plan_ref="customer360.plan",
            parameters=(("pytransformkit.plan_ref", "other"),),
        )


def test_lot19_transform_owned_retry_forbids_workflow_retry_multiplication() -> None:
    with pytest.raises(PyTransformKitRetryOwnershipError):
        pytransformkit_v2_task(
            key="transform",
            plan_ref="customer360.plan",
            retry_owner=PyTransformKitRetryOwner.PYTRANSFORMKIT,
            retry_policy=RetryPolicy(max_attempts=2),
        )


def test_lot19_pyworkflowkit_owned_retry_can_create_next_attempt() -> None:
    job = _RetryThenSuccessTransform()
    task = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        retry_owner=PyTransformKitRetryOwner.PYWORKFLOWKIT,
        retry_policy=RetryPolicy(max_attempts=2),
    )

    result, metadata = _run_transform_task(task, job)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert job.calls == 2
    assert result.task("transform").output["resource_id"] == "customer360-v2"
    task_run = metadata.list_task_runs(result.run_id)[0]
    assert len(metadata.list_task_attempts(task_run.task_run_id)) == 2


def test_lot19_success_receives_portable_dependency_outputs_and_persists_evidence() -> None:
    job = _SuccessTransform()
    ingest_customers = TaskDefinition(
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
        dependencies=("ingest_customers",),
        credential_ref="secretref://transform/customer360",
    )

    result, metadata = _run_transform_task(
        transform,
        job,
        upstream=(ingest_customers,),
    )

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert job.inputs == {
        "ingest_customers": {
            "kind": "pyingestkit.dataset_version_reference",
            "dataset_id": "customers",
            "version": "2026-10-03",
        }
    }
    assert result.task("transform").output["uri"] == "resource://customer360/v1"

    transform_run = next(
        item for item in metadata.list_task_runs(result.run_id) if item.task_key == "transform"
    )
    attempt = metadata.list_task_attempts(transform_run.task_run_id)[0]
    refs = metadata.list_external_run_refs(attempt.attempt_id)
    assert len(refs) == 1
    assert refs[0].provider == "pytransformkit"
    assert refs[0].kind == "transformation_execution"
    assert dict(refs[0].metadata)["plan_ref"] == "customer360.plan"
    assert "credential_ref" not in dict(refs[0].metadata)

    checkpoint = metadata.get_task_output_checkpoint(transform_run.task_run_id)
    assert checkpoint.output["kind"] == "pytransformkit.resource_reference"


def test_lot19_confirmed_failure_is_known_provider_failure() -> None:
    task = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
    )

    result, metadata = _run_transform_task(task, _KnownFailureTransform())

    assert result.status is WorkflowRunStatus.FAILED
    assert result.failure is not None
    assert result.failure.category is FailureCategory.EXTERNAL_PROVIDER
    assert result.failure.retryability is Retryability.NON_RETRYABLE
    assert result.failure.uncertainty is OutcomeUncertainty.KNOWN
    assert result.failure.external_run is not None
    assert result.failure.external_run.external_run_id == "TRANSFORM-FAILED"

    task_run = metadata.list_task_runs(result.run_id)[0]
    attempt = metadata.list_task_attempts(task_run.task_run_id)[0]
    refs = metadata.list_external_run_refs(attempt.attempt_id)
    assert refs[0].provider == "pytransformkit"


def test_lot19_unknown_outcome_requires_reconciliation_without_blind_retry() -> None:
    task = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        retry_owner=PyTransformKitRetryOwner.PYWORKFLOWKIT,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    result, metadata = _run_transform_task(task, _UnknownTransform())

    assert result.status is WorkflowRunStatus.UNKNOWN_OUTCOME
    assert result.failure is not None
    assert result.failure.category is FailureCategory.UNKNOWN_OUTCOME
    assert result.failure.retryability is Retryability.RETRYABLE_AFTER_RECONCILIATION
    assert result.failure.uncertainty is OutcomeUncertainty.REQUIRES_RECONCILIATION

    task_run = metadata.list_task_runs(result.run_id)[0]
    attempts = metadata.list_task_attempts(task_run.task_run_id)
    assert len(attempts) == 1
    refs = metadata.list_external_run_refs(attempts[0].attempt_id)
    assert refs[0].external_run_id == "TRANSFORM-UNKNOWN"


def test_lot19_nonportable_dependency_fails_before_sibling_execution() -> None:
    job = _MustNotRunTransform()
    upstream = TaskDefinition(key="upstream", workload=lambda: object())
    transform = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        dependencies=("upstream",),
    )

    result, _ = _run_transform_task(transform, job, upstream=(upstream,))

    assert result.status is WorkflowRunStatus.FAILED
    assert result.failure is not None
    assert result.failure.error_code == "PWK-PYTRANSFORMKIT-NONPORTABLE-INPUT"
    assert result.failure.category is FailureCategory.CONTRACT_VIOLATION
    assert job.calls == 0


def test_lot19_wrapper_exception_fails_closed() -> None:
    task = pytransformkit_v2_task(
        key="transform",
        plan_ref="customer360.plan",
        retry_owner=PyTransformKitRetryOwner.PYWORKFLOWKIT,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    result, metadata = _run_transform_task(task, _ExplodingTransform())

    assert result.status is WorkflowRunStatus.FAILED
    assert result.failure is not None
    assert result.failure.error_code == "PWK-PYTRANSFORMKIT-WRAPPER-EXCEPTION"
    assert result.failure.retryability is Retryability.NON_RETRYABLE
    task_run = metadata.list_task_runs(result.run_id)[0]
    assert len(metadata.list_task_attempts(task_run.task_run_id)) == 1


def test_lot19_invalid_wrapper_result_fails_closed() -> None:
    task = pytransformkit_v2_task(key="transform", plan_ref="customer360.plan")

    result, _ = _run_transform_task(task, _InvalidTransformResult())

    assert result.status is WorkflowRunStatus.FAILED
    assert result.failure is not None
    assert result.failure.error_code == "PWK-PYTRANSFORMKIT-RESULT-CONTRACT"


def test_lot19_result_and_resource_contract_versions_fail_closed() -> None:
    with pytest.raises(ValueError, match="resource contract version"):
        PyTransformKitResourceReference(
            resource_id="resource",
            uri="resource://x",
            contract_version="999",
        )

    with pytest.raises(ValueError, match="integration contract version"):
        PyTransformKitExecutionResult(
            external_run_id="run-1",
            status=PyTransformKitExecutionStatus.FAILED,
            error_code="failed",
            contract_version="999",
        )


def test_lot19_result_validates_success_and_failure_shapes() -> None:
    with pytest.raises(ValueError, match="requires resource"):
        PyTransformKitExecutionResult(
            external_run_id="run-1",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
        )
    with pytest.raises(ValueError, match="cannot define error fields"):
        PyTransformKitExecutionResult(
            external_run_id="run-1",
            status=PyTransformKitExecutionStatus.SUCCEEDED,
            resource=PyTransformKitResourceReference(
                resource_id="resource",
                uri="resource://x",
            ),
            error_code="unexpected",
        )
    with pytest.raises(ValueError, match="requires error_code"):
        PyTransformKitExecutionResult(
            external_run_id="run-1",
            status=PyTransformKitExecutionStatus.FAILED,
        )


def test_lot19_binding_targets_exact_registered_workload_key() -> None:
    workload = PyTransformKitWorkload(plan_ref="customer360.plan")
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
    assert snapshot["atomic_plan_boundary"] is True
    assert snapshot["imports_pytransformkit"] is False
    assert snapshot["portable_dependency_handoff"] is True
    assert snapshot["resource_reference_output"] is True
    assert snapshot["unknown_outcome_requires_reconciliation"] is True
    assert snapshot["raw_credentials_supported"] is False
    assert snapshot["implicit_retry_multiplication"] is False
