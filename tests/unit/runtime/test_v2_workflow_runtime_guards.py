"""Negative and injectable-service tests for LOT-06 WorkflowRuntime."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pyworkflowkit.authoring import RegisteredWorkload, TaskDefinition, WorkflowDefinition
from pyworkflowkit.errors import ExecutorNotFoundError, RuntimeInvariantError
from pyworkflowkit.executors import (
    ExecutorDescriptor,
    ExecutorRegistry,
    InlineExecutor,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
    WorkflowRuntime,
)


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 10, 2, 15, 0, tzinfo=UTC)


class NaiveClock:
    def now(self) -> datetime:
        return datetime(2026, 10, 2, 15, 0)


class BadClock:
    def now(self) -> object:
        return "not-a-datetime"


class FixedIds:
    def new_workflow_run_id(self) -> WorkflowRunId:
        return WorkflowRunId.parse("W-fixed")

    def new_task_run_id(self) -> TaskRunId:
        return TaskRunId.parse("TR-fixed")

    def new_task_attempt_id(self) -> TaskAttemptId:
        return TaskAttemptId.parse("TA-fixed")

    def new_correlation_id(self) -> CorrelationId:
        return CorrelationId.parse("C-fixed")


class EmptyCapabilityExecutor:
    @property
    def descriptor(self) -> ExecutorDescriptor:
        return ExecutorDescriptor(
            executor_id="inline",
            display_name="Empty",
            executor_version="1",
            supported_workload_kinds=(),
        )

    def execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        del request
        return TaskExecutionResult()


class ExplodingExecutor:
    @property
    def descriptor(self) -> ExecutorDescriptor:
        return ExecutorDescriptor(
            executor_id="inline",
            display_name="Exploding",
            executor_version="1",
            supported_workload_kinds=("python_callable",),
        )

    def execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        del request
        raise RuntimeError("executor exploded")


class InvalidResultExecutor:
    @property
    def descriptor(self) -> ExecutorDescriptor:
        return ExecutorDescriptor(
            executor_id="inline",
            display_name="Invalid Result",
            executor_version="1",
            supported_workload_kinds=("python_callable",),
        )

    def execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        del request
        return object()  # type: ignore[return-value]


def _workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="guard",
        tasks=(TaskDefinition(key="a", workload=lambda: 1),),
    )


def test_runtime_constructor_rejects_non_protocol_dependencies() -> None:
    with pytest.raises(TypeError, match="executor"):
        WorkflowRuntime(
            executor=object(),  # type: ignore[arg-type]
            metadata=InMemoryMetadataStore(),
        )

    with pytest.raises(TypeError, match="metadata"):
        WorkflowRuntime(
            executor=InlineExecutor(),
            metadata=object(),  # type: ignore[arg-type]
        )


def test_runtime_constructor_accepts_registry_and_rejects_empty_or_invalid_registry() -> None:
    registry = ExecutorRegistry((InlineExecutor(),))
    runtime = WorkflowRuntime(
        executor_registry=registry,
        metadata=InMemoryMetadataStore(),
    )
    assert runtime.executor_registry is registry

    with pytest.raises(TypeError, match="executor or executor_registry"):
        WorkflowRuntime(metadata=InMemoryMetadataStore())

    with pytest.raises(TypeError, match="executor_registry"):
        WorkflowRuntime(
            executor_registry=object(),  # type: ignore[arg-type]
            metadata=InMemoryMetadataStore(),
        )

    with pytest.raises(ValueError, match="at least one executor"):
        WorkflowRuntime(
            executor_registry=ExecutorRegistry(),
            metadata=InMemoryMetadataStore(),
        )


def test_runtime_rejects_invalid_run_input() -> None:
    runtime = WorkflowRuntime(
        executor=InlineExecutor(),
        metadata=InMemoryMetadataStore(),
    )

    with pytest.raises(TypeError, match="WorkflowDefinition or ExecutionPlan"):
        runtime.run(object())  # type: ignore[arg-type]


def test_preflight_rejects_executor_key_mismatch_before_persistence() -> None:
    store = InMemoryMetadataStore()
    workflow = WorkflowDefinition(
        name="executor-mismatch",
        tasks=(
            TaskDefinition(
                key="a",
                workload=RegisteredWorkload("job", executor_key="thread"),
            ),
        ),
    )
    runtime = WorkflowRuntime(
        executor=InlineExecutor({"job": lambda: None}),
        metadata=store,
    )

    with pytest.raises(ExecutorNotFoundError):
        runtime.run(workflow)

    assert store.list_workflow_runs() == ()


def test_preflight_rejects_unsupported_workload_kind_before_persistence() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(
        executor=EmptyCapabilityExecutor(),
        metadata=store,
    )

    with pytest.raises(RuntimeInvariantError, match="does not support workload kind"):
        runtime.run(_workflow())

    assert store.list_workflow_runs() == ()


def test_unexpected_executor_exception_becomes_failed_workflow_result() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(
        executor=ExplodingExecutor(),
        metadata=store,
        clock=FixedClock(),
        identity_factory=FixedIds(),
    )

    result = runtime.run(_workflow())

    assert result.status.value == "FAILED"
    assert result.failure is not None
    assert result.failure.error_code == "RuntimeError"
    assert result.failure.message_summary == "executor exploded"
    assert result.failure.workflow_run_id == "W-fixed"
    assert result.failure.task_run_id == "TR-fixed"
    assert result.failure.task_attempt_id == "TA-fixed"


def test_executor_returning_wrong_result_type_fails_runtime_invariant() -> None:
    runtime = WorkflowRuntime(
        executor=InvalidResultExecutor(),
        metadata=InMemoryMetadataStore(),
        clock=FixedClock(),
        identity_factory=FixedIds(),
    )

    with pytest.raises(RuntimeInvariantError, match="TaskExecutionResult"):
        runtime.run(_workflow())


@pytest.mark.parametrize("clock", [NaiveClock(), BadClock()])
def test_runtime_rejects_invalid_clock_values(clock: object) -> None:
    runtime = WorkflowRuntime(
        executor=InlineExecutor(),
        metadata=InMemoryMetadataStore(),
        clock=clock,  # type: ignore[arg-type]
        identity_factory=FixedIds(),
    )

    with pytest.raises((TypeError, ValueError), match="clock.now"):
        runtime.run(_workflow())


def test_explicit_correlation_is_preserved_and_bound_to_runtime_identity() -> None:
    correlation = CorrelationContext(
        correlation_id=CorrelationId.parse("C-user"),
        causation_id="parent-action",
        trace_id="trace-1",
    )
    result = WorkflowRuntime(
        executor=InlineExecutor(),
        metadata=InMemoryMetadataStore(),
        clock=FixedClock(),
        identity_factory=FixedIds(),
    ).run(_workflow(), correlation=correlation)

    assert result.correlation.correlation_id == CorrelationId.parse("C-user")
    assert result.correlation.causation_id == "parent-action"
    assert result.correlation.trace_id == "trace-1"
    assert result.correlation.workflow_run_id == "W-fixed"
