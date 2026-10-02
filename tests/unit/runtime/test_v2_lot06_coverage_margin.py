"""Coverage margin for LOT-06 boundary validation guards."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pyworkflowkit.authoring import WorkloadPortability
from pyworkflowkit.executors import (
    ExecutorDescriptor,
    InlineExecutor,
    TaskExecutionContext,
    TaskExecutionRequest,
)
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    TaskAttemptId,
    TaskOutcome,
    TaskRunId,
    WorkflowResult,
    WorkflowRunId,
)
from pyworkflowkit.states import TaskRunStatus, WorkflowRunStatus


def _context(**overrides: object) -> TaskExecutionContext:
    values: dict[str, object] = {
        "workflow_run_id": WorkflowRunId.parse("W"),
        "task_run_id": TaskRunId.parse("TR"),
        "attempt_id": TaskAttemptId.parse("TA"),
        "attempt_number": 1,
        "correlation": CorrelationContext(correlation_id=CorrelationId.parse("C")),
    }
    values.update(overrides)
    return TaskExecutionContext(**values)  # type: ignore[arg-type]


def _outcome() -> TaskOutcome:
    return TaskOutcome(
        task_key="task",
        task_run_id=TaskRunId.parse("TR"),
        status=TaskRunStatus.SUCCEEDED,
    )


def _workflow_result(**overrides: object) -> WorkflowResult:
    values: dict[str, object] = {
        "run_id": WorkflowRunId.parse("W"),
        "status": WorkflowRunStatus.SUCCEEDED,
        "task_outcomes": (_outcome(),),
        "diagnostics": (),
        "correlation": CorrelationContext(correlation_id=CorrelationId.parse("C")),
    }
    values.update(overrides)
    return WorkflowResult(**values)  # type: ignore[arg-type]


def test_executor_descriptor_rejects_non_string_identity() -> None:
    with pytest.raises(TypeError, match="executor_id"):
        ExecutorDescriptor(
            executor_id=1,  # type: ignore[arg-type]
            display_name="Inline",
            executor_version="1",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("workflow_run_id", "W", "workflow_run_id"),
        ("task_run_id", "TR", "task_run_id"),
        ("attempt_id", "TA", "attempt_id"),
        ("correlation", "C", "correlation"),
    ),
)
def test_execution_context_rejects_wrong_runtime_identity_types(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        _context(**{field: value})


def test_task_outcome_rejects_wrong_status_and_diagnostics_types() -> None:
    with pytest.raises(TypeError, match="status"):
        TaskOutcome(
            task_key="task",
            task_run_id=TaskRunId.parse("TR"),
            status="SUCCEEDED",  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="diagnostics"):
        TaskOutcome(
            task_key="task",
            task_run_id=TaskRunId.parse("TR"),
            status=TaskRunStatus.SUCCEEDED,
            diagnostics=(object(),),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    (
        ({"run_id": "W"}, "run_id"),
        ({"status": "SUCCEEDED"}, "status"),
        ({"correlation": "C"}, "correlation"),
    ),
)
def test_workflow_result_rejects_wrong_boundary_types(
    overrides: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(TypeError, match=message):
        _workflow_result(**overrides)


class _DescriptorWorkload:
    @property
    def workload_kind(self) -> str:
        return "custom"

    @property
    def portability(self) -> WorkloadPortability:
        return WorkloadPortability.LOCAL_ONLY

    def fingerprint_payload(self) -> Mapping[str, object]:
        return {"kind": "custom"}


class _UninspectableCallable:
    __signature__ = object()

    def __call__(self) -> None:
        return None


def test_inline_executor_guards_invalid_registration_and_request_type() -> None:
    executor = InlineExecutor()

    with pytest.raises(ValueError, match="must not be empty"):
        executor.register("", lambda: None)

    with pytest.raises(TypeError, match="TaskExecutionRequest"):
        executor.execute(object())  # type: ignore[arg-type]


def test_inline_executor_reports_unresolved_descriptor_workload() -> None:
    result = InlineExecutor().execute(
        TaskExecutionRequest(
            task_key="custom",
            workload=_DescriptorWorkload(),
            executor_key="inline",
            context=_context(),
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_code == "PWK-INLINE-WORKLOAD-UNRESOLVED"


def test_inline_executor_reports_uninspectable_callable_signature() -> None:
    result = InlineExecutor().execute(
        TaskExecutionRequest(
            task_key="bad-signature",
            workload=_UninspectableCallable(),
            executor_key="inline",
            context=_context(),
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_code == "PWK-INLINE-HANDLER-CONTRACT"
