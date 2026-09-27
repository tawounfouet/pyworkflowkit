"""M47 unit coverage for generic external workload interoperability."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from pyworkflowkit.domain.enums import TimeoutMode
from pyworkflowkit.domain.ids import TaskAttemptId, TaskId, TaskRunId, WorkflowRunId
from pyworkflowkit.domain.values import RetryPolicy
from pyworkflowkit.errors import (
    ExternalWorkloadError,
    ExternalWorkloadRetryOwnershipError,
)
from pyworkflowkit.integrations.workload import (
    EXTERNAL_WORKLOAD_CONTRACT_VERSION,
    ExternalRetryOwner,
    ExternalWorkloadAdapter,
    ExternalWorkloadResult,
    external_workload_task,
)
from pyworkflowkit.ports.executor import RunContext


def _context() -> RunContext:
    return RunContext(
        workflow_run_id=WorkflowRunId("workflow-run"),
        task_run_id=TaskRunId("task-run"),
        attempt_id=TaskAttemptId("attempt"),
        task_id=TaskId("external"),
        attempt_number=1,
    )


@dataclass
class SuccessfulWorkload:
    calls: int = 0

    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        self.calls += 1
        assert context.task_id == TaskId("external")
        return ExternalWorkloadResult(
            external_run_id="foreign-42",
            succeeded=True,
            output={"rows": 12},
            uri="https://example.test/runs/foreign-42",
            metadata={"dataset": "customers"},
        )


def test_external_workload_contract_version_is_v1() -> None:
    assert EXTERNAL_WORKLOAD_CONTRACT_VERSION == "1"


def test_adapter_construction_is_side_effect_free_and_success_is_normalized() -> None:
    workload = SuccessfulWorkload()
    adapter = ExternalWorkloadAdapter(
        workload=workload,
        provider="acme",
        workload_ref="customers.refresh",
    )

    assert workload.calls == 0

    result = adapter(_context())

    assert workload.calls == 1
    assert result.output == {"rows": 12}
    assert result.metadata["external_workload_provider"] == "acme"
    assert result.metadata["external_workload_ref"] == "customers.refresh"
    assert result.external_refs[0].provider == "acme"
    assert result.external_refs[0].external_run_id == "foreign-42"
    assert result.external_refs[0].metadata["workload_ref"] == "customers.refresh"
    assert result.external_refs[0].metadata["retry_owner"] == "external"


def test_adapter_normalizes_foreign_exception() -> None:
    class BrokenWorkload:
        def run(self, *, context: RunContext) -> ExternalWorkloadResult:
            raise ConnectionError("service unavailable")

    adapter = ExternalWorkloadAdapter(
        workload=BrokenWorkload(),
        provider="acme",
        workload_ref="customers.refresh",
    )

    with pytest.raises(ExternalWorkloadError) as caught:
        adapter(_context())

    assert caught.value.provider == "acme"
    assert caught.value.error_type == "ConnectionError"
    assert caught.value.error_category == "ConnectionError"


def test_adapter_normalizes_failed_foreign_run() -> None:
    class FailedWorkload:
        def run(self, *, context: RunContext) -> ExternalWorkloadResult:
            return ExternalWorkloadResult(
                external_run_id="foreign-failed",
                succeeded=False,
                error_type="RemoteValidationError",
                error_message="schema mismatch",
                error_category="validation",
            )

    adapter = ExternalWorkloadAdapter(
        workload=FailedWorkload(),
        provider="acme",
        workload_ref="customers.refresh",
    )

    with pytest.raises(ExternalWorkloadError) as caught:
        adapter(_context())

    assert caught.value.external_run_id == "foreign-failed"
    assert caught.value.error_type == "RemoteValidationError"
    assert caught.value.error_category == "validation"


def test_external_owned_retry_rejects_nested_pyworkflowkit_retry() -> None:
    with pytest.raises(ExternalWorkloadRetryOwnershipError):
        external_workload_task(
            id="external",
            provider="acme",
            workload_ref="customers.refresh",
            workload=SuccessfulWorkload(),
            retry_owner=ExternalRetryOwner.EXTERNAL,
            retry_policy=RetryPolicy(max_attempts=2),
        )


def test_pyworkflowkit_can_explicitly_own_retry() -> None:
    handle = external_workload_task(
        id="external",
        provider="acme",
        workload_ref="customers.refresh",
        workload=SuccessfulWorkload(),
        retry_owner=ExternalRetryOwner.PYWORKFLOWKIT,
        retry_policy=RetryPolicy(max_attempts=2),
    )

    assert handle.retry_policy.max_attempts == 2


def test_timeout_and_executor_semantics_remain_task_executor_concerns() -> None:
    handle = external_workload_task(
        id="external",
        provider="acme",
        workload_ref="customers.refresh",
        workload=SuccessfulWorkload(),
        executor_key="thread",
        timeout_seconds=5.0,
        timeout_mode=TimeoutMode.SOFT,
    )

    assert handle.executor_key == "thread"
    assert handle.timeout_seconds == 5.0
    assert handle.timeout_mode is TimeoutMode.SOFT


@pytest.mark.parametrize(
    "result",
    [
        ExternalWorkloadResult(
            external_run_id="ok",
            succeeded=True,
        ),
        ExternalWorkloadResult(
            external_run_id="failed",
            succeeded=False,
            error_type="RemoteFailure",
        ),
    ],
)
def test_normalized_result_metadata_is_immutable(result: ExternalWorkloadResult) -> None:
    with pytest.raises(TypeError):
        result.metadata["mutate"] = True  # type: ignore[index]
