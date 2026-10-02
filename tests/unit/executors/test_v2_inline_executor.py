"""LOT-06 unit tests for the canonical V2 InlineExecutor."""

from __future__ import annotations

from datetime import UTC, datetime

from pyworkflowkit.authoring import RegisteredWorkload
from pyworkflowkit.diagnostics import FailureCategory
from pyworkflowkit.executors import (
    Executor,
    InlineExecutor,
    TaskExecutionContext,
    TaskExecutionRequest,
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
        workflow_run_id=WorkflowRunId.parse("W-1"),
        task_run_id=TaskRunId.parse("TR-1"),
        attempt_id=TaskAttemptId.parse("TA-1"),
        attempt_number=1,
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-1"),
        ),
    )


def test_inline_executor_satisfies_v2_protocol() -> None:
    assert isinstance(InlineExecutor(), Executor)
    assert InlineExecutor().descriptor.executor_id == "inline"
    assert InlineExecutor().descriptor.supported_workload_kinds == (
        "python_callable",
        "registered",
    )


def test_inline_executor_invokes_zero_argument_callable() -> None:
    executor = InlineExecutor()
    request = TaskExecutionRequest(
        task_key="extract",
        workload=lambda: 42,
        executor_key="inline",
        context=_context(),
    )

    result = executor.execute(request)

    assert result.succeeded is True
    assert result.output == 42
    assert result.failure is None


def test_inline_executor_passes_execution_context_to_one_argument_callable() -> None:
    executor = InlineExecutor()

    def transform(context: TaskExecutionContext) -> int:
        return int(context.dependency_outputs["extract"]) * 2

    request = TaskExecutionRequest(
        task_key="transform",
        workload=transform,
        executor_key="inline",
        context=TaskExecutionContext(
            workflow_run_id=WorkflowRunId.parse("W-1"),
            task_run_id=TaskRunId.parse("TR-1"),
            attempt_id=TaskAttemptId.parse("TA-1"),
            attempt_number=1,
            correlation=CorrelationContext(
                correlation_id=CorrelationId.parse("C-1"),
            ),
            dependency_outputs={"extract": 21},
        ),
    )

    assert executor.execute(request).output == 42


def test_registered_workload_uses_explicit_binding_and_parameters() -> None:
    def registered(context: TaskExecutionContext) -> str:
        return context.workload_parameters["mode"]

    executor = InlineExecutor({"jobs.customer": registered})
    request = TaskExecutionRequest(
        task_key="customer",
        workload=RegisteredWorkload(
            "jobs.customer",
            parameters=(("mode", "full"),),
        ),
        executor_key="inline",
        context=_context(),
    )

    result = executor.execute(request)

    assert result.succeeded is True
    assert result.output == "full"


def test_missing_registered_workload_is_structured_capability_failure() -> None:
    result = InlineExecutor().execute(
        TaskExecutionRequest(
            task_key="missing",
            workload=RegisteredWorkload("jobs.missing"),
            executor_key="inline",
            context=_context(),
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.category is FailureCategory.CAPABILITY


def test_workload_exception_becomes_failure_evidence() -> None:
    def explode() -> None:
        raise ValueError("boom")

    result = InlineExecutor().execute(
        TaskExecutionRequest(
            task_key="explode",
            workload=explode,
            executor_key="inline",
            context=_context(),
        )
    )

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_code == "ValueError"
    assert result.failure.message_summary == "boom"
    assert result.failure.task_attempt_id == "TA-1"


def test_dependency_outputs_are_read_only_mapping() -> None:
    context = TaskExecutionContext(
        workflow_run_id=WorkflowRunId.parse("W-1"),
        task_run_id=TaskRunId.parse("TR-1"),
        attempt_id=TaskAttemptId.parse("TA-1"),
        attempt_number=1,
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-1"),
        ),
        dependency_outputs={"a": 1},
    )

    try:
        context.dependency_outputs["a"] = 2  # type: ignore[index]
    except TypeError:
        pass
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("dependency_outputs must be read-only")


def test_failure_evidence_timestamp_is_timezone_aware() -> None:
    def explode() -> None:
        raise RuntimeError("boom")

    failure = (
        InlineExecutor()
        .execute(
            TaskExecutionRequest(
                task_key="explode",
                workload=explode,
                executor_key="inline",
                context=_context(),
            )
        )
        .failure
    )

    assert failure is not None
    assert isinstance(failure.occurred_at, datetime)
    assert failure.occurred_at.tzinfo is UTC
