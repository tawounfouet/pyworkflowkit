"""Tests for the optional PyIngestKit anti-corruption adapter."""

from dataclasses import dataclass

import pytest

from pyworkflowkit.domain.ids import TaskAttemptId, TaskId, TaskRunId, WorkflowRunId
from pyworkflowkit.domain.values import RetryPolicy
from pyworkflowkit.errors import (
    PyIngestKitAdapterError,
    PyIngestKitRetryOwnershipError,
)
from pyworkflowkit.integrations.pyingestkit import (
    PyIngestKitRetryOwner,
    PyIngestKitRunResult,
    PyIngestKitTaskAdapter,
    pyingestkit_task,
)
from pyworkflowkit.ports.executor import RunContext


def _context() -> RunContext:
    return RunContext(
        workflow_run_id=WorkflowRunId("workflow-run"),
        task_run_id=TaskRunId("task-run"),
        attempt_id=TaskAttemptId("attempt"),
        task_id=TaskId("ingest"),
        attempt_number=1,
    )


@dataclass
class SuccessfulJob:
    def run(self, *, context: RunContext) -> PyIngestKitRunResult:
        assert context.task_id == TaskId("ingest")
        return PyIngestKitRunResult(
            external_run_id="ingestion-42",
            succeeded=True,
            output={"rows": 12},
            uri="https://example.test/runs/ingestion-42",
            metadata={"dataset": "customers"},
        )


def test_adapter_translates_success_to_task_result_and_external_ref() -> None:
    adapter = PyIngestKitTaskAdapter(
        job=SuccessfulJob(),
        job_ref="customers.refresh",
    )

    result = adapter(_context())

    assert result.output == {"rows": 12}
    assert result.external_refs[0].provider == "pyingestkit"
    assert result.external_refs[0].external_run_id == "ingestion-42"
    assert result.external_refs[0].metadata["job_ref"] == "customers.refresh"


def test_adapter_translates_foreign_exception_to_public_integration_error() -> None:
    class BrokenJob:
        def run(self, *, context: RunContext) -> PyIngestKitRunResult:
            raise ConnectionError("source unavailable")

    adapter = PyIngestKitTaskAdapter(
        job=BrokenJob(),
        job_ref="customers.refresh",
    )

    with pytest.raises(PyIngestKitAdapterError, match="source unavailable"):
        adapter(_context())


def test_adapter_translates_failed_external_run() -> None:
    class FailedJob:
        def run(self, *, context: RunContext) -> PyIngestKitRunResult:
            return PyIngestKitRunResult(
                external_run_id="ingestion-failed",
                succeeded=False,
                error_type="SourceValidationError",
                error_message="schema mismatch",
                error_category="validation",
            )

    adapter = PyIngestKitTaskAdapter(
        job=FailedJob(),
        job_ref="customers.refresh",
    )

    with pytest.raises(PyIngestKitAdapterError, match="schema mismatch"):
        adapter(_context())


def test_pyingestkit_owned_retry_rejects_nested_pyworkflowkit_retry() -> None:
    with pytest.raises(PyIngestKitRetryOwnershipError):
        pyingestkit_task(
            id="ingest",
            job_ref="customers.refresh",
            job=SuccessfulJob(),
            retry_owner=PyIngestKitRetryOwner.PYINGESTKIT,
            retry_policy=RetryPolicy(max_attempts=2),
        )


def test_pyworkflowkit_can_explicitly_own_retry() -> None:
    handle = pyingestkit_task(
        id="ingest",
        job_ref="customers.refresh",
        job=SuccessfulJob(),
        retry_owner=PyIngestKitRetryOwner.PYWORKFLOWKIT,
        retry_policy=RetryPolicy(max_attempts=2),
    )

    assert handle.retry_policy.max_attempts == 2
