"""LOT-08 timeout and cancellation runtime conformance."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Event, Thread

import pytest

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.diagnostics import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.executors import (
    CancellationCapability,
    CancellationStatus,
    ExecutorDescriptor,
    TaskCancellationRequest,
    TaskCancellationResult,
    TaskExecutionRequest,
    TaskExecutionResult,
)
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.policies import RetryPolicy, TimeoutPolicy
from pyworkflowkit.runtime import WorkflowResult, WorkflowRuntime
from pyworkflowkit.states import (
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)


class DeadlineExecutor:
    def __init__(self, *, uncertain: bool = False, succeed_after_timeout: bool = False) -> None:
        self.uncertain = uncertain
        self.succeed_after_timeout = succeed_after_timeout
        self.calls = 0
        self.deadlines: list[datetime | None] = []

    @property
    def descriptor(self) -> ExecutorDescriptor:
        return ExecutorDescriptor(
            executor_id="inline",
            display_name="Deadline test executor",
            executor_version="1",
            supported_workload_kinds=("python_callable",),
            supports_execution_timeout=True,
        )

    def execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        self.calls += 1
        self.deadlines.append(request.deadline_at)
        if self.succeed_after_timeout and self.calls > 1:
            return TaskExecutionResult(output="recovered")

        uncertainty = (
            OutcomeUncertainty.REQUIRES_RECONCILIATION
            if self.uncertain
            else OutcomeUncertainty.KNOWN
        )
        retryability = (
            Retryability.RETRYABLE_AFTER_RECONCILIATION
            if self.uncertain
            else Retryability.RETRYABLE
            if self.succeed_after_timeout
            else Retryability.NON_RETRYABLE
        )
        return TaskExecutionResult(
            failure=FailureEvidence(
                error_code="PWK-DEADLINE",
                category=FailureCategory.TIMEOUT,
                retryability=retryability,
                uncertainty=uncertainty,
                correlation_id=request.context.correlation.correlation_id,
                workflow_run_id=str(request.context.workflow_run_id),
                task_run_id=str(request.context.task_run_id),
                task_attempt_id=str(request.context.attempt_id),
                message_summary="execution deadline exceeded",
            )
        )


class BlockingCancellableExecutor:
    def __init__(self, status: CancellationStatus) -> None:
        self.started = Event()
        self.release = Event()
        self.status = status
        self.cancel_requests: list[TaskCancellationRequest] = []

    @property
    def descriptor(self) -> ExecutorDescriptor:
        return ExecutorDescriptor(
            executor_id="inline",
            display_name="Blocking cancellable executor",
            executor_version="1",
            supported_workload_kinds=("python_callable",),
            cancellation_capability=CancellationCapability.CONFIRMED,
        )

    def execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        self.started.set()
        self.release.wait(timeout=5)
        return TaskExecutionResult(output="finished")

    def cancel(self, request: TaskCancellationRequest) -> TaskCancellationResult:
        self.cancel_requests.append(request)
        self.release.set()
        return TaskCancellationResult(
            status=self.status,
            attempt_id=request.attempt_id,
            reason=f"executor_{self.status.value}",
        )


def _workflow(*, timeout: float | None = None, retries: int = 1) -> WorkflowDefinition:
    return WorkflowDefinition(
        name="lot08",
        tasks=(
            TaskDefinition(
                key="work",
                workload=lambda: "unused",
                retry_policy=RetryPolicy(max_attempts=retries),
                timeout_policy=TimeoutPolicy(execution_timeout=timeout),
            ),
        ),
    )


def test_confirmed_timeout_is_distinct_terminal_timeout() -> None:
    store = InMemoryMetadataStore()
    executor = DeadlineExecutor()
    runtime = WorkflowRuntime(executor=executor, metadata=store)

    result = runtime.run(_workflow(timeout=2.0))

    assert result.status is WorkflowRunStatus.TIMED_OUT
    task = store.list_task_runs(result.run_id)[0]
    attempt = store.list_task_attempts(task.task_run_id)[0]
    assert task.status is TaskRunStatus.TIMED_OUT
    assert attempt.status is TaskAttemptStatus.TIMED_OUT
    assert executor.deadlines[0] is not None
    assert executor.deadlines[0].tzinfo is UTC


def test_confirmed_timeout_can_retry_with_new_attempt_identity() -> None:
    store = InMemoryMetadataStore()
    executor = DeadlineExecutor(succeed_after_timeout=True)
    runtime = WorkflowRuntime(executor=executor, metadata=store)

    result = runtime.run(_workflow(timeout=1.0, retries=2))

    assert result.status is WorkflowRunStatus.SUCCEEDED
    task = store.list_task_runs(result.run_id)[0]
    attempts = store.list_task_attempts(task.task_run_id)
    assert tuple(attempt.status for attempt in attempts) == (
        TaskAttemptStatus.TIMED_OUT,
        TaskAttemptStatus.SUCCEEDED,
    )
    assert attempts[0].attempt_id != attempts[1].attempt_id
    assert attempts[0].task_run_id == attempts[1].task_run_id


def test_uncertain_timeout_requires_reconciliation_instead_of_failure() -> None:
    store = InMemoryMetadataStore()
    executor = DeadlineExecutor(uncertain=True)
    runtime = WorkflowRuntime(executor=executor, metadata=store)

    result = runtime.run(_workflow(timeout=1.0, retries=4))

    assert result.status is WorkflowRunStatus.UNKNOWN_OUTCOME
    task = store.list_task_runs(result.run_id)[0]
    attempt = store.list_task_attempts(task.task_run_id)[0]
    assert task.status is TaskRunStatus.UNKNOWN_OUTCOME
    assert attempt.status is TaskAttemptStatus.REQUIRES_RECONCILIATION
    assert len(store.list_task_attempts(task.task_run_id)) == 1


def test_workflow_cancellation_confirmed_is_not_only_requested() -> None:
    store = InMemoryMetadataStore()
    executor = BlockingCancellableExecutor(CancellationStatus.CONFIRMED)
    runtime = WorkflowRuntime(executor=executor, metadata=store)
    results: list[WorkflowResult] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            results.append(runtime.run(_workflow()))
        except BaseException as exc:  # pragma: no cover - failure capture
            errors.append(exc)

    thread = Thread(target=run)
    thread.start()
    assert executor.started.wait(timeout=5)

    run_id = store.list_workflow_runs()[0].run_id
    cancellation = runtime.cancel(run_id)

    thread.join(timeout=5)
    assert not thread.is_alive()
    assert errors == []
    assert cancellation.status is CancellationStatus.CONFIRMED
    assert results[0].status is WorkflowRunStatus.CANCELLED

    task = store.list_task_runs(run_id)[0]
    attempt = store.list_task_attempts(task.task_run_id)[0]
    assert task.status is TaskRunStatus.CANCELLED
    assert attempt.status is TaskAttemptStatus.CANCELLED
    assert len(executor.cancel_requests) == 1


def test_unconfirmed_cancellation_preserves_unknown_outcome() -> None:
    store = InMemoryMetadataStore()
    executor = BlockingCancellableExecutor(CancellationStatus.UNCONFIRMED)
    runtime = WorkflowRuntime(executor=executor, metadata=store)

    thread = Thread(target=lambda: runtime.run(_workflow()))
    thread.start()
    assert executor.started.wait(timeout=5)

    run_id = store.list_workflow_runs()[0].run_id
    cancellation = runtime.cancel(run_id)

    assert cancellation.status is CancellationStatus.UNCONFIRMED
    assert store.get_workflow_run(run_id).status is WorkflowRunStatus.UNKNOWN_OUTCOME

    executor.release.set()
    thread.join(timeout=5)


def test_cancel_is_idempotent_for_terminal_workflow() -> None:
    store = InMemoryMetadataStore()
    from pyworkflowkit.executors import InlineExecutor

    runtime = WorkflowRuntime(
        executor=InlineExecutor(),
        metadata=store,
    )
    result = runtime.run(_workflow())

    cancellation = runtime.cancel(result.run_id)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert cancellation.status is CancellationStatus.ALREADY_TERMINAL


def test_cancel_task_before_execution_is_confirmed_without_executor_call() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=DeadlineExecutor(), metadata=store)

    with pytest.raises(TypeError, match="TaskRunId"):
        runtime.cancel_task("TR-invalid")  # type: ignore[arg-type]


def test_unsupported_active_cancellation_is_explicit_and_does_not_fake_cancel() -> None:
    from pyworkflowkit.executors import InlineExecutor

    store = InMemoryMetadataStore()
    started = Event()
    release = Event()
    results: list[WorkflowResult] = []

    def blocking() -> str:
        started.set()
        release.wait(timeout=5)
        return "done"

    workflow = WorkflowDefinition(
        name="unsupported-cancel",
        tasks=(TaskDefinition(key="work", workload=blocking),),
    )
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)

    thread = Thread(target=lambda: results.append(runtime.run(workflow)))
    thread.start()
    assert started.wait(timeout=5)

    run_id = store.list_workflow_runs()[0].run_id
    cancellation = runtime.cancel(run_id)

    assert cancellation.status is CancellationStatus.UNSUPPORTED
    assert store.get_workflow_run(run_id).status is WorkflowRunStatus.CANCELLATION_REQUESTED

    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert results[0].status is WorkflowRunStatus.CANCELLED

    task = store.list_task_runs(run_id)[0]
    attempt = store.list_task_attempts(task.task_run_id)[0]
    assert task.status is TaskRunStatus.SUCCEEDED
    assert attempt.status is TaskAttemptStatus.SUCCEEDED
