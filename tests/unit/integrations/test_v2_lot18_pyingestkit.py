"""LOT-18 unit qualification for the canonical V2 PyIngestKit boundary."""

from __future__ import annotations

import pytest

from pyworkflowkit.authoring import RegisteredWorkload, WorkflowDefinition
from pyworkflowkit.diagnostics import (
    FailureCategory,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.integrations.pyingestkit import (
    V2_PYINGESTKIT_INTEGRATION_CONTRACT_VERSION,
    PyIngestKitExecutionResult,
    PyIngestKitExecutionStatus,
    PyIngestKitRetryOwner,
    PyIngestKitWorkload,
    PyIngestKitWorkloadHandler,
    pyingestkit_v2_task,
    pyingestkit_v2_workload_binding,
    v2_pyingestkit_integration_snapshot,
)
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.planning import WorkflowPlanner
from pyworkflowkit.policies import RetryPolicy
from pyworkflowkit.runtime import WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus


class _SuccessJob:
    def run(self, *, context):
        return PyIngestKitExecutionResult(
            external_run_id=f"ingest-{context.attempt_id}",
            status=PyIngestKitExecutionStatus.SUCCEEDED,
            output={"rows": 3},
            metadata=(("dataset", "customers"),),
        )


class _KnownFailureJob:
    def run(self, *, context):
        del context
        return PyIngestKitExecutionResult(
            external_run_id="INGEST-FAILED",
            status=PyIngestKitExecutionStatus.FAILED,
            error_code="INGEST-500",
            provider_code="500",
            message_summary="provider rejected ingestion",
            retryable=False,
        )


class _UnknownOutcomeJob:
    def run(self, *, context):
        del context
        return PyIngestKitExecutionResult(
            external_run_id="INGEST-UNKNOWN",
            status=PyIngestKitExecutionStatus.UNKNOWN_OUTCOME,
            status_locator="https://provider.invalid/runs/INGEST-UNKNOWN",
            error_code="INGEST-UNKNOWN",
            message_summary="submission acknowledged but final outcome is unknown",
        )


class _RetryThenSuccessJob:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, *, context):
        self.calls += 1
        if self.calls == 1:
            return PyIngestKitExecutionResult(
                external_run_id=f"retry-{context.attempt_id}",
                status=PyIngestKitExecutionStatus.FAILED,
                error_code="INGEST-TRANSIENT",
                message_summary="temporary provider failure",
                retryable=True,
            )
        return PyIngestKitExecutionResult(
            external_run_id=f"retry-{context.attempt_id}",
            status=PyIngestKitExecutionStatus.SUCCEEDED,
            output={"rows": 5},
        )


class _ExplodingJob:
    def run(self, *, context):
        del context
        raise RuntimeError("wrapper exploded")


class _InvalidResultJob:
    def run(self, *, context):
        del context
        return object()


def _run_single_task(task, job):
    workload = task.workload
    assert isinstance(workload, PyIngestKitWorkload)
    binding = pyingestkit_v2_workload_binding(workload=workload, job=job)
    executor = InlineExecutor({binding.registry_key: binding.handler})
    metadata = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=executor, metadata=metadata)
    result = runtime.run(
        WorkflowDefinition(
            name="lot18",
            version="1",
            tasks=(task,),
        )
    )
    return result, metadata


def test_lot18_workload_is_portable_registered_workload_and_planner_integration() -> None:
    task = pyingestkit_v2_task(
        key="ingest_customers",
        job_ref="customers.daily",
        parameters=(("mode", "incremental"),),
        credential_ref="secretref://ingest/customers",
    )

    workload = task.workload
    assert isinstance(workload, PyIngestKitWorkload)
    assert isinstance(workload, RegisteredWorkload)
    assert workload.registry_key == "pyingestkit:customers.daily"
    assert workload.job_ref == "customers.daily"
    assert workload.retry_owner is PyIngestKitRetryOwner.PYINGESTKIT
    assert workload.credential_ref == "secretref://ingest/customers"
    assert task.portable is True

    plan = WorkflowPlanner().compile(WorkflowDefinition(name="lot18-plan", tasks=(task,)))
    assert plan.required_integrations == ("pyingestkit",)
    assert plan.task("ingest_customers").required_integrations == ("pyingestkit",)
    assert plan.task("ingest_customers").executor_requirement.workload_kind == "registered"


def test_lot18_workload_fingerprint_contains_integration_semantics() -> None:
    workload = PyIngestKitWorkload(
        job_ref="orders.full",
        parameters=(("mode", "full"),),
        retry_owner=PyIngestKitRetryOwner.PYWORKFLOWKIT,
        credential_ref="credential://orders",
    )

    payload = workload.fingerprint_payload()

    assert payload["integration_key"] == "pyingestkit"
    assert payload["job_ref"] == "orders.full"
    assert payload["retry_owner"] == "pyworkflowkit"
    assert payload["credential_ref"] == "credential://orders"


def test_lot18_reserved_parameters_cannot_be_overridden() -> None:
    with pytest.raises(ValueError, match="reserved PyIngestKit"):
        PyIngestKitWorkload(
            job_ref="customers",
            parameters=(("pyingestkit.job_ref", "other"),),
        )


def test_lot18_pyingestkit_owned_retry_forbids_workflow_retry_multiplication() -> None:
    with pytest.raises(Exception, match="retry"):
        pyingestkit_v2_task(
            key="ingest",
            job_ref="customers",
            retry_owner=PyIngestKitRetryOwner.PYINGESTKIT,
            retry_policy=RetryPolicy(max_attempts=2),
        )


def test_lot18_pyworkflowkit_owned_retry_allows_multiple_attempts() -> None:
    task = pyingestkit_v2_task(
        key="ingest",
        job_ref="customers",
        retry_owner=PyIngestKitRetryOwner.PYWORKFLOWKIT,
        retry_policy=RetryPolicy(max_attempts=2),
    )

    result, metadata = _run_single_task(task, _RetryThenSuccessJob())

    assert result.status is WorkflowRunStatus.SUCCEEDED
    outcome = result.task("ingest")
    assert len(outcome.attempt_ids) == 2
    assert outcome.output == {"rows": 5}
    task_run = metadata.list_task_runs(result.run_id)[0]
    assert len(metadata.list_task_attempts(task_run.task_run_id)) == 2


def test_lot18_success_persists_external_run_and_portable_output() -> None:
    task = pyingestkit_v2_task(
        key="ingest",
        job_ref="customers",
        credential_ref="secretref://customers",
    )

    result, metadata = _run_single_task(task, _SuccessJob())

    assert result.status is WorkflowRunStatus.SUCCEEDED
    outcome = result.task("ingest")
    assert outcome.output == {"rows": 3}

    task_run = metadata.list_task_runs(result.run_id)[0]
    attempts = metadata.list_task_attempts(task_run.task_run_id)
    refs = metadata.list_external_run_refs(attempts[0].attempt_id)
    assert len(refs) == 1
    assert refs[0].provider == "pyingestkit"
    assert refs[0].kind == "ingestion"
    assert refs[0].status_hint == "succeeded"
    assert dict(refs[0].metadata)["job_ref"] == "customers"
    assert "credential_ref" not in dict(refs[0].metadata)
    checkpoint = metadata.get_task_output_checkpoint(task_run.task_run_id)
    assert checkpoint.output["rows"] == 3


def test_lot18_confirmed_failure_is_known_and_non_retryable() -> None:
    task = pyingestkit_v2_task(key="ingest", job_ref="customers")

    result, metadata = _run_single_task(task, _KnownFailureJob())

    assert result.status is WorkflowRunStatus.FAILED
    failure = result.failure
    assert failure is not None
    assert failure.category is FailureCategory.EXTERNAL_PROVIDER
    assert failure.retryability is Retryability.NON_RETRYABLE
    assert failure.uncertainty is OutcomeUncertainty.KNOWN
    assert failure.external_run is not None
    assert failure.external_run.external_run_id == "INGEST-FAILED"

    task_run = metadata.list_task_runs(result.run_id)[0]
    attempt = metadata.list_task_attempts(task_run.task_run_id)[0]
    assert metadata.list_external_run_refs(attempt.attempt_id)[0].external_run_id == "INGEST-FAILED"


def test_lot18_unknown_outcome_requires_reconciliation_without_blind_retry() -> None:
    task = pyingestkit_v2_task(
        key="ingest",
        job_ref="customers",
        retry_owner=PyIngestKitRetryOwner.PYWORKFLOWKIT,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    result, metadata = _run_single_task(task, _UnknownOutcomeJob())

    assert result.status is WorkflowRunStatus.UNKNOWN_OUTCOME
    failure = result.failure
    assert failure is not None
    assert failure.category is FailureCategory.UNKNOWN_OUTCOME
    assert failure.retryability is Retryability.RETRYABLE_AFTER_RECONCILIATION
    assert failure.uncertainty is OutcomeUncertainty.REQUIRES_RECONCILIATION

    task_run = metadata.list_task_runs(result.run_id)[0]
    attempts = metadata.list_task_attempts(task_run.task_run_id)
    assert len(attempts) == 1
    refs = metadata.list_external_run_refs(attempts[0].attempt_id)
    assert refs[0].external_run_id == "INGEST-UNKNOWN"


def test_lot18_wrapper_exception_fails_closed_without_retry() -> None:
    task = pyingestkit_v2_task(
        key="ingest",
        job_ref="customers",
        retry_owner=PyIngestKitRetryOwner.PYWORKFLOWKIT,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    result, metadata = _run_single_task(task, _ExplodingJob())

    assert result.status is WorkflowRunStatus.FAILED
    assert result.failure is not None
    assert result.failure.category is FailureCategory.CONTRACT_VIOLATION
    assert result.failure.retryability is Retryability.NON_RETRYABLE
    task_run = metadata.list_task_runs(result.run_id)[0]
    assert len(metadata.list_task_attempts(task_run.task_run_id)) == 1


def test_lot18_invalid_wrapper_result_fails_closed() -> None:
    task = pyingestkit_v2_task(key="ingest", job_ref="customers")

    result, _ = _run_single_task(task, _InvalidResultJob())

    assert result.status is WorkflowRunStatus.FAILED
    assert result.failure is not None
    assert result.failure.error_code == "PWK-PYINGESTKIT-RESULT-CONTRACT"


def test_lot18_execution_result_rejects_incompatible_contract_version() -> None:
    with pytest.raises(ValueError, match="unsupported PyIngestKit V2"):
        PyIngestKitExecutionResult(
            external_run_id="run-1",
            status=PyIngestKitExecutionStatus.SUCCEEDED,
            contract_version="999",
        )



def test_lot21_workload_rejects_incompatible_integration_contract_version() -> None:
    with pytest.raises(ValueError, match="unsupported PyIngestKit V2"):
        PyIngestKitWorkload(
            job_ref="jobs.customer360",
            contract_version="999",
        )


def test_lot18_execution_result_validates_failure_shape() -> None:
    with pytest.raises(ValueError, match="requires error_code"):
        PyIngestKitExecutionResult(
            external_run_id="run-1",
            status=PyIngestKitExecutionStatus.FAILED,
        )
    with pytest.raises(ValueError, match="cannot define error fields"):
        PyIngestKitExecutionResult(
            external_run_id="run-1",
            status=PyIngestKitExecutionStatus.SUCCEEDED,
            error_code="unexpected",
        )


def test_lot18_binding_targets_exact_registered_workload_key() -> None:
    workload = PyIngestKitWorkload(job_ref="customers")
    binding = pyingestkit_v2_workload_binding(workload=workload, job=_SuccessJob())

    assert binding.registry_key == workload.registry_key
    assert isinstance(binding.handler, PyIngestKitWorkloadHandler)


def test_lot18_snapshot_freezes_boundary_posture() -> None:
    snapshot = v2_pyingestkit_integration_snapshot()

    assert snapshot["contract_version"] == V2_PYINGESTKIT_INTEGRATION_CONTRACT_VERSION
    assert snapshot["integration_key"] == "pyingestkit"
    assert snapshot["atomic_job_boundary"] is True
    assert snapshot["imports_pyingestkit"] is False
    assert snapshot["unknown_outcome_requires_reconciliation"] is True
    assert snapshot["raw_credentials_supported"] is False
    assert snapshot["credential_reference_supported"] is True
    assert snapshot["implicit_retry_multiplication"] is False
