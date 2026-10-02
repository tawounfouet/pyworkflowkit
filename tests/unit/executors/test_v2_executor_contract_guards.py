"""Guard and negative tests for LOT-06 executor contracts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pyworkflowkit.authoring import RegisteredWorkload
from pyworkflowkit.diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.executors import (
    CancellationCapability,
    CancellationStatus,
    ExecutorDescriptor,
    InlineExecutor,
    TaskCancellationRequest,
    TaskCancellationResult,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
)


def _context() -> TaskExecutionContext:
    return TaskExecutionContext(
        workflow_run_id=WorkflowRunId.parse("W-guard"),
        task_run_id=TaskRunId.parse("TR-guard"),
        attempt_id=TaskAttemptId.parse("TA-guard"),
        attempt_number=1,
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-guard"),
        ),
    )


def _failure() -> FailureEvidence:
    return FailureEvidence(
        error_code="E-GUARD",
        category=FailureCategory.INTERNAL,
        retryability=Retryability.NON_RETRYABLE,
        uncertainty=OutcomeUncertainty.KNOWN,
        correlation_id=CorrelationId.parse("C-guard"),
        occurred_at=datetime(2026, 10, 2, 15, 0, tzinfo=UTC),
    )


def test_executor_descriptor_normalizes_sequence_fields() -> None:
    descriptor = ExecutorDescriptor(
        executor_id="inline",
        display_name="Inline",
        executor_version="1",
        capabilities=("z", "a", "a"),
        execution_modes=("sync", "sync"),
        portability_constraints=("local",),
        supported_workload_kinds=("registered", "python_callable"),
    )

    assert descriptor.capabilities == ("a", "z")
    assert descriptor.execution_modes == ("sync",)
    assert descriptor.supported_workload_kinds == ("python_callable", "registered")


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("executor_id", {"executor_id": ""}),
        ("display_name", {"display_name": ""}),
        ("executor_version", {"executor_version": ""}),
    ],
)
def test_executor_descriptor_rejects_empty_identity_fields(
    field_name: str,
    kwargs: dict[str, str],
) -> None:
    values = {
        "executor_id": "inline",
        "display_name": "Inline",
        "executor_version": "1",
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=field_name):
        ExecutorDescriptor(**values)


def test_executor_descriptor_rejects_invalid_capability_text() -> None:
    with pytest.raises(ValueError, match="capabilities"):
        ExecutorDescriptor(
            executor_id="inline",
            display_name="Inline",
            executor_version="1",
            capabilities=("",),
        )


@pytest.mark.parametrize("attempt_number", [0, -1])
def test_execution_context_rejects_non_positive_attempt_number(
    attempt_number: int,
) -> None:
    with pytest.raises(ValueError, match="attempt_number"):
        TaskExecutionContext(
            workflow_run_id=WorkflowRunId.parse("W-1"),
            task_run_id=TaskRunId.parse("TR-1"),
            attempt_id=TaskAttemptId.parse("TA-1"),
            attempt_number=attempt_number,
            correlation=CorrelationContext(
                correlation_id=CorrelationId.parse("C-1"),
            ),
        )


def test_execution_context_rejects_boolean_attempt_number() -> None:
    with pytest.raises(TypeError, match="attempt_number"):
        TaskExecutionContext(
            workflow_run_id=WorkflowRunId.parse("W-1"),
            task_run_id=TaskRunId.parse("TR-1"),
            attempt_id=TaskAttemptId.parse("TA-1"),
            attempt_number=True,
            correlation=CorrelationContext(
                correlation_id=CorrelationId.parse("C-1"),
            ),
        )


def test_execution_context_rejects_invalid_mapping_keys_and_values() -> None:
    with pytest.raises(ValueError, match="dependency output key"):
        TaskExecutionContext(
            workflow_run_id=WorkflowRunId.parse("W-1"),
            task_run_id=TaskRunId.parse("TR-1"),
            attempt_id=TaskAttemptId.parse("TA-1"),
            attempt_number=1,
            correlation=CorrelationContext(
                correlation_id=CorrelationId.parse("C-1"),
            ),
            dependency_outputs={"": 1},
        )

    with pytest.raises(TypeError, match="workload parameter values"):
        TaskExecutionContext(
            workflow_run_id=WorkflowRunId.parse("W-1"),
            task_run_id=TaskRunId.parse("TR-1"),
            attempt_id=TaskAttemptId.parse("TA-1"),
            attempt_number=1,
            correlation=CorrelationContext(
                correlation_id=CorrelationId.parse("C-1"),
            ),
            workload_parameters={"mode": 1},  # type: ignore[dict-item]
        )


def test_execution_request_rejects_invalid_workload_and_context() -> None:
    with pytest.raises(TypeError, match="workload"):
        TaskExecutionRequest(
            task_key="a",
            workload=object(),  # type: ignore[arg-type]
            executor_key="inline",
            context=_context(),
        )

    with pytest.raises(TypeError, match="context"):
        TaskExecutionRequest(
            task_key="a",
            workload=lambda: None,
            executor_key="inline",
            context=object(),  # type: ignore[arg-type]
        )


def test_execution_result_validates_failure_and_diagnostics() -> None:
    failure = _failure()
    result = TaskExecutionResult(failure=failure)

    assert result.succeeded is False

    with pytest.raises(TypeError, match="failure"):
        TaskExecutionResult(failure=object())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="diagnostics"):
        TaskExecutionResult(diagnostics=(object(),))  # type: ignore[arg-type]

    diagnostic = Diagnostic(
        code="PWK-TEST",
        severity=DiagnosticSeverity.INFO,
        summary="guard",
    )
    assert TaskExecutionResult(diagnostics=(diagnostic,)).diagnostics == (diagnostic,)


def test_inline_executor_rejects_duplicate_or_non_callable_bindings() -> None:
    executor = InlineExecutor({"job": lambda: None})

    with pytest.raises(ValueError, match="already exists"):
        executor.register("job", lambda: None)

    with pytest.raises(TypeError, match="callable"):
        executor.register("other", object())  # type: ignore[arg-type]


def test_inline_executor_rejects_mismatched_executor_request() -> None:
    result = InlineExecutor().execute(
        TaskExecutionRequest(
            task_key="a",
            workload=lambda: 1,
            executor_key="thread",
            context=_context(),
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.category is FailureCategory.CAPABILITY
    assert result.failure.error_code == "PWK-EXECUTOR-MISMATCH"


@pytest.mark.parametrize(
    "handler",
    [
        lambda one, two: None,
        lambda *args: None,
        lambda **kwargs: None,
    ],
)
def test_inline_executor_rejects_unsupported_handler_signatures(handler: object) -> None:
    result = InlineExecutor().execute(
        TaskExecutionRequest(
            task_key="bad-signature",
            workload=handler,  # type: ignore[arg-type]
            executor_key="inline",
            context=_context(),
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.category is FailureCategory.CONTRACT_VIOLATION


def test_inline_executor_preserves_explicit_task_execution_result() -> None:
    expected = TaskExecutionResult(output={"ok": True})

    def workload() -> TaskExecutionResult:
        return expected

    actual = InlineExecutor().execute(
        TaskExecutionRequest(
            task_key="a",
            workload=workload,
            executor_key="inline",
            context=_context(),
        )
    )

    assert actual is expected


def test_registered_workload_binding_constructor_rejects_non_callable() -> None:
    with pytest.raises(TypeError, match="callable"):
        InlineExecutor({"job": object()})  # type: ignore[dict-item]


def test_missing_registered_workload_keeps_failure_identity() -> None:
    result = InlineExecutor().execute(
        TaskExecutionRequest(
            task_key="missing",
            workload=RegisteredWorkload("missing"),
            executor_key="inline",
            context=_context(),
        )
    )

    assert result.failure is not None
    assert result.failure.workflow_run_id == "W-guard"
    assert result.failure.task_run_id == "TR-guard"
    assert result.failure.task_attempt_id == "TA-guard"


def test_executor_descriptor_rejects_non_boolean_retry_ownership_flag() -> None:
    with pytest.raises(TypeError, match="performs_implicit_workload_retry"):
        ExecutorDescriptor(
            executor_id="inline",
            display_name="Inline",
            executor_version="1",
            performs_implicit_workload_retry=1,  # type: ignore[arg-type]
        )


def test_execution_request_validates_deadline_boundary() -> None:
    naive = datetime(2026, 10, 2, 18, 0)

    with pytest.raises(ValueError, match="timezone-aware"):
        TaskExecutionRequest(
            task_key="a",
            workload=lambda: None,
            executor_key="inline",
            context=_context(),
            deadline_at=naive,
        )

    aware = datetime(2026, 10, 2, 18, 0, tzinfo=UTC)
    request = TaskExecutionRequest(
        task_key="a",
        workload=lambda: None,
        executor_key="inline",
        context=_context(),
        deadline_at=aware,
    )
    assert request.deadline_at == aware


def test_executor_descriptor_validates_timeout_and_cancellation_capabilities() -> None:
    descriptor = ExecutorDescriptor(
        executor_id="deadline",
        display_name="Deadline",
        executor_version="1",
        supports_execution_timeout=True,
        cancellation_capability=CancellationCapability.CONFIRMED,
    )

    assert descriptor.supports_execution_timeout is True
    assert descriptor.cancellation_capability is CancellationCapability.CONFIRMED

    with pytest.raises(TypeError, match="supports_execution_timeout"):
        ExecutorDescriptor(
            executor_id="bad",
            display_name="Bad",
            executor_version="1",
            supports_execution_timeout=1,  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="cancellation_capability"):
        ExecutorDescriptor(
            executor_id="bad",
            display_name="Bad",
            executor_version="1",
            cancellation_capability="confirmed",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("workflow_run_id", "W", "workflow_run_id"),
        ("task_run_id", "TR", "task_run_id"),
        ("attempt_id", "TA", "attempt_id"),
        ("requested_at", "now", "requested_at"),
    ),
)
def test_task_cancellation_request_rejects_invalid_identity_fields(
    field: str,
    value: object,
    message: str,
) -> None:
    values: dict[str, object] = {
        "workflow_run_id": WorkflowRunId.parse("W"),
        "task_run_id": TaskRunId.parse("TR"),
        "attempt_id": TaskAttemptId.parse("TA"),
        "task_key": "task",
        "requested_at": datetime(2026, 10, 2, 18, 0, tzinfo=UTC),
    }
    values[field] = value

    with pytest.raises((TypeError, ValueError), match=message):
        TaskCancellationRequest(**values)  # type: ignore[arg-type]


def test_task_cancellation_request_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        TaskCancellationRequest(
            workflow_run_id=WorkflowRunId.parse("W"),
            task_run_id=TaskRunId.parse("TR"),
            attempt_id=TaskAttemptId.parse("TA"),
            task_key="task",
            requested_at=datetime(2026, 10, 2, 18, 0),
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("status", "confirmed", "status"),
        ("attempt_id", "TA", "attempt_id"),
        ("reason", "", "reason"),
        ("diagnostics", (object(),), "diagnostics"),
    ),
)
def test_task_cancellation_result_rejects_invalid_values(
    field: str,
    value: object,
    message: str,
) -> None:
    values: dict[str, object] = {
        "status": CancellationStatus.CONFIRMED,
        "attempt_id": TaskAttemptId.parse("TA"),
        "reason": "confirmed",
        "diagnostics": (),
    }
    values[field] = value

    with pytest.raises((TypeError, ValueError), match=message):
        TaskCancellationResult(**values)  # type: ignore[arg-type]
