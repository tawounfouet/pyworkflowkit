"""LOT-07 runtime tests for attempt-scoped retry execution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.diagnostics import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.errors import RuntimeInvariantError
from pyworkflowkit.executors import (
    ExecutorDescriptor,
    InlineExecutor,
    TaskExecutionContext,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.policies import (
    BackoffStrategy,
    RetryPolicy,
)
from pyworkflowkit.runtime import (
    Clock,
    CorrelationId,
    RetryWaiter,
    RuntimeIdentityFactory,
    TaskAttemptId,
    TaskRunId,
    WorkflowRunId,
    WorkflowRuntime,
)
from pyworkflowkit.states import (
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)


class StepClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 10, 2, 16, 0, tzinfo=UTC)

    def now(self) -> datetime:
        current = self.value
        self.value += timedelta(milliseconds=10)
        return current


class FixedIds:
    def __init__(self) -> None:
        self.workflow = 0
        self.task = 0
        self.attempt = 0
        self.correlation = 0

    def new_workflow_run_id(self) -> WorkflowRunId:
        self.workflow += 1
        return WorkflowRunId.parse(f"W-{self.workflow}")

    def new_task_run_id(self) -> TaskRunId:
        self.task += 1
        return TaskRunId.parse(f"TR-{self.task}")

    def new_task_attempt_id(self) -> TaskAttemptId:
        self.attempt += 1
        return TaskAttemptId.parse(f"TA-{self.attempt}")

    def new_correlation_id(self) -> CorrelationId:
        self.correlation += 1
        return CorrelationId.parse(f"C-{self.correlation}")


class RecordingWaiter:
    def __init__(self) -> None:
        self.delays: list[float] = []

    def wait(self, seconds: float) -> None:
        self.delays.append(seconds)


def _runtime(
    store: InMemoryMetadataStore,
    *,
    executor: object | None = None,
    waiter: RecordingWaiter | None = None,
) -> WorkflowRuntime:
    clock = StepClock()
    ids = FixedIds()
    actual_waiter = waiter or RecordingWaiter()
    assert isinstance(clock, Clock)
    assert isinstance(ids, RuntimeIdentityFactory)
    assert isinstance(actual_waiter, RetryWaiter)
    return WorkflowRuntime(
        executor=executor or InlineExecutor(),  # type: ignore[arg-type]
        metadata=store,
        clock=clock,
        identity_factory=ids,
        retry_waiter=actual_waiter,
    )


def _retryable_failure(context: TaskExecutionContext) -> FailureEvidence:
    return FailureEvidence(
        error_code="E-TRANSIENT",
        category=FailureCategory.TRANSIENT,
        retryability=Retryability.RETRYABLE,
        uncertainty=OutcomeUncertainty.KNOWN,
        correlation_id=context.correlation.correlation_id,
        workflow_run_id=str(context.workflow_run_id),
        task_run_id=str(context.task_run_id),
        task_attempt_id=str(context.attempt_id),
        source_component="test_workload",
        message_summary="temporary",
    )


def test_retry_reuses_task_run_and_creates_new_attempt_identity() -> None:
    store = InMemoryMetadataStore()
    waiter = RecordingWaiter()
    calls = 0

    def flaky(context: TaskExecutionContext) -> TaskExecutionResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            return TaskExecutionResult(failure=_retryable_failure(context))
        return TaskExecutionResult(output="ok")

    workflow = WorkflowDefinition(
        name="retry-success",
        tasks=(
            TaskDefinition(
                key="flaky",
                workload=flaky,
                retry_policy=RetryPolicy(
                    max_attempts=3,
                    backoff_strategy=BackoffStrategy.FIXED,
                    initial_delay_seconds=2.5,
                    retryable_failure_categories=frozenset(
                        {FailureCategory.TRANSIENT}
                    ),
                ),
            ),
        ),
    )

    result = _runtime(store, waiter=waiter).run(workflow)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert result.task("flaky").status is TaskRunStatus.SUCCEEDED
    assert result.task("flaky").output == "ok"
    assert waiter.delays == [2.5]

    task_run = store.list_task_runs(result.run_id)[0]
    attempts = store.list_task_attempts(task_run.task_run_id)

    assert len(attempts) == 2
    assert attempts[0].task_run_id == attempts[1].task_run_id == task_run.task_run_id
    assert attempts[0].attempt_id != attempts[1].attempt_id
    assert tuple(attempt.attempt_number for attempt in attempts) == (1, 2)
    assert attempts[0].status is TaskAttemptStatus.FAILED
    assert attempts[1].status is TaskAttemptStatus.SUCCEEDED

    codes = tuple(diagnostic.code for diagnostic in result.diagnostics)
    assert "PWK-RETRY-DECISION" in codes
    assert "PWK-RETRY-SCHEDULED" in codes


def test_non_retryable_failure_does_not_create_second_attempt() -> None:
    store = InMemoryMetadataStore()

    def fatal(context: TaskExecutionContext) -> TaskExecutionResult:
        return TaskExecutionResult(
            failure=FailureEvidence(
                error_code="E-FATAL",
                category=FailureCategory.INTEGRITY,
                retryability=Retryability.NON_RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                correlation_id=context.correlation.correlation_id,
            )
        )

    workflow = WorkflowDefinition(
        name="no-retry",
        tasks=(
            TaskDefinition(
                key="fatal",
                workload=fatal,
                retry_policy=RetryPolicy(max_attempts=5),
            ),
        ),
    )

    result = _runtime(store).run(workflow)
    task_run = store.list_task_runs(result.run_id)[0]

    assert result.status is WorkflowRunStatus.FAILED
    assert task_run.status is TaskRunStatus.FAILED
    assert len(store.list_task_attempts(task_run.task_run_id)) == 1


def test_retry_exhaustion_closes_task_only_after_last_attempt() -> None:
    store = InMemoryMetadataStore()

    def always_transient(context: TaskExecutionContext) -> TaskExecutionResult:
        return TaskExecutionResult(failure=_retryable_failure(context))

    workflow = WorkflowDefinition(
        name="exhaustion",
        tasks=(
            TaskDefinition(
                key="a",
                workload=always_transient,
                retry_policy=RetryPolicy(max_attempts=3),
            ),
        ),
    )

    result = _runtime(store).run(workflow)
    task_run = store.list_task_runs(result.run_id)[0]
    attempts = store.list_task_attempts(task_run.task_run_id)

    assert result.status is WorkflowRunStatus.FAILED
    assert task_run.status is TaskRunStatus.FAILED
    assert tuple(attempt.attempt_number for attempt in attempts) == (1, 2, 3)
    assert all(attempt.status is TaskAttemptStatus.FAILED for attempt in attempts)


def test_uncertain_failure_returns_recoverable_unknown_outcome_without_retry() -> None:
    store = InMemoryMetadataStore()
    waiter = RecordingWaiter()

    def uncertain(context: TaskExecutionContext) -> TaskExecutionResult:
        return TaskExecutionResult(
            failure=FailureEvidence(
                error_code="E-UNKNOWN",
                category=FailureCategory.UNKNOWN_OUTCOME,
                retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
                uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
                correlation_id=context.correlation.correlation_id,
                workflow_run_id=str(context.workflow_run_id),
                task_run_id=str(context.task_run_id),
                task_attempt_id=str(context.attempt_id),
            )
        )

    workflow = WorkflowDefinition(
        name="unknown",
        tasks=(
            TaskDefinition(
                key="external",
                workload=uncertain,
                retry_policy=RetryPolicy(max_attempts=5),
            ),
            TaskDefinition(
                key="downstream",
                workload=lambda: "must-not-run",
                dependencies=("external",),
            ),
        ),
    )

    result = _runtime(store, waiter=waiter).run(workflow)

    assert result.status is WorkflowRunStatus.UNKNOWN_OUTCOME
    assert waiter.delays == []

    runs = {task.task_key: task for task in store.list_task_runs(result.run_id)}
    attempts = store.list_task_attempts(runs["external"].task_run_id)

    assert runs["external"].status is TaskRunStatus.UNKNOWN_OUTCOME
    assert runs["downstream"].status is TaskRunStatus.PENDING
    assert len(attempts) == 1
    assert attempts[0].status is TaskAttemptStatus.REQUIRES_RECONCILIATION
    assert store.list_task_attempts(runs["downstream"].task_run_id) == ()


class ImplicitRetryExecutor:
    @property
    def descriptor(self) -> ExecutorDescriptor:
        return ExecutorDescriptor(
            executor_id="inline",
            display_name="Implicit retry executor",
            executor_version="1",
            supported_workload_kinds=("python_callable",),
            performs_implicit_workload_retry=True,
        )

    def execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        raise AssertionError("preflight must reject retry amplification")


def test_runtime_rejects_stacked_equivalent_retry_scope() -> None:
    store = InMemoryMetadataStore()
    workflow = WorkflowDefinition(
        name="amplification",
        tasks=(
            TaskDefinition(
                key="a",
                workload=lambda: None,
                retry_policy=RetryPolicy(max_attempts=2),
            ),
        ),
    )

    import pytest

    with pytest.raises(RuntimeInvariantError, match="implicit workload retry"):
        _runtime(store, executor=ImplicitRetryExecutor()).run(workflow)

    assert store.list_workflow_runs() == ()
