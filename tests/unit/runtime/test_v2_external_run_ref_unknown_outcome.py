"""LOT-09 tests for attempt-scoped external execution evidence."""

from __future__ import annotations

from threading import Event, Thread

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
from pyworkflowkit.policies import RetryPolicy
from pyworkflowkit.runtime import ExternalRunRef, WorkflowRuntime
from pyworkflowkit.states import (
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)


class ExternalEvidenceExecutor:
    """Test executor producing one foreign execution identity per attempt."""

    def __init__(self, *outcomes: str) -> None:
        self._outcomes = outcomes or ("success",)
        self.calls = 0

    @property
    def descriptor(self) -> ExecutorDescriptor:
        return ExecutorDescriptor(
            executor_id="inline",
            display_name="LOT-09 external evidence executor",
            executor_version="1",
            supported_workload_kinds=("python_callable",),
        )

    def execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        outcome = self._outcomes[min(self.calls, len(self._outcomes) - 1)]
        self.calls += 1
        external_ref = ExternalRunRef(
            provider="remote-test",
            kind="job",
            external_run_id=f"JOB-{request.context.attempt_number}",
            correlation_id=request.context.correlation.correlation_id,
            status_locator=f"memory://remote/JOB-{request.context.attempt_number}",
        )

        if outcome == "success":
            return TaskExecutionResult(
                output=f"ok-{request.context.attempt_number}",
                external_runs=(external_ref,),
            )

        if outcome == "retryable":
            failure = FailureEvidence(
                error_code="REMOTE-TRANSIENT",
                category=FailureCategory.TRANSIENT,
                retryability=Retryability.RETRYABLE,
                uncertainty=OutcomeUncertainty.KNOWN,
                correlation_id=request.context.correlation.correlation_id,
                workflow_run_id=str(request.context.workflow_run_id),
                task_run_id=str(request.context.task_run_id),
                task_attempt_id=str(request.context.attempt_id),
                external_run=external_ref,
                source_component="external_test_executor",
            )
            return TaskExecutionResult(
                failure=failure,
                external_runs=(external_ref,),
            )

        if outcome == "uncertain":
            failure = FailureEvidence(
                error_code="REMOTE-UNKNOWN",
                category=FailureCategory.UNKNOWN_OUTCOME,
                retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
                uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
                correlation_id=request.context.correlation.correlation_id,
                workflow_run_id=str(request.context.workflow_run_id),
                task_run_id=str(request.context.task_run_id),
                task_attempt_id=str(request.context.attempt_id),
                external_run=external_ref,
                source_component="external_test_executor",
            )
            return TaskExecutionResult(
                failure=failure,
                external_runs=(external_ref,),
            )

        raise AssertionError(f"unsupported test outcome: {outcome}")


def _workflow(*, max_attempts: int = 1) -> WorkflowDefinition:
    return WorkflowDefinition(
        name="lot09",
        tasks=(
            TaskDefinition(
                key="external",
                workload=lambda: None,
                retry_policy=RetryPolicy(max_attempts=max_attempts),
            ),
        ),
    )


def test_successful_external_execution_persists_attempt_scoped_reference() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(
        executor=ExternalEvidenceExecutor("success"),
        metadata=store,
    )

    result = runtime.run(_workflow())

    assert result.status is WorkflowRunStatus.SUCCEEDED
    task_run = store.list_task_runs(result.run_id)[0]
    attempt = store.list_task_attempts(task_run.task_run_id)[0]
    refs = store.list_external_run_refs(attempt.attempt_id)

    assert task_run.status is TaskRunStatus.SUCCEEDED
    assert attempt.status is TaskAttemptStatus.SUCCEEDED
    assert len(refs) == 1
    assert refs[0].provider == "remote-test"
    assert refs[0].kind == "job"
    assert refs[0].external_run_id == "JOB-1"


def test_unknown_outcome_retains_external_identity_without_blind_retry() -> None:
    store = InMemoryMetadataStore()
    executor = ExternalEvidenceExecutor("uncertain")
    runtime = WorkflowRuntime(executor=executor, metadata=store)

    result = runtime.run(_workflow(max_attempts=5))

    assert result.status is WorkflowRunStatus.UNKNOWN_OUTCOME
    task_run = store.list_task_runs(result.run_id)[0]
    attempts = store.list_task_attempts(task_run.task_run_id)

    assert task_run.status is TaskRunStatus.UNKNOWN_OUTCOME
    assert len(attempts) == 1
    assert attempts[0].status is TaskAttemptStatus.REQUIRES_RECONCILIATION
    assert executor.calls == 1

    refs = store.list_external_run_refs(attempts[0].attempt_id)
    assert len(refs) == 1
    assert refs[0].external_run_id == "JOB-1"


def test_retry_keeps_external_refs_scoped_to_the_attempt_that_created_them() -> None:
    store = InMemoryMetadataStore()
    executor = ExternalEvidenceExecutor("retryable", "success")
    runtime = WorkflowRuntime(executor=executor, metadata=store)

    result = runtime.run(_workflow(max_attempts=2))

    assert result.status is WorkflowRunStatus.SUCCEEDED
    task_run = store.list_task_runs(result.run_id)[0]
    attempts = store.list_task_attempts(task_run.task_run_id)

    assert tuple(attempt.status for attempt in attempts) == (
        TaskAttemptStatus.FAILED,
        TaskAttemptStatus.SUCCEEDED,
    )
    assert tuple(
        store.list_external_run_refs(attempt.attempt_id)[0].external_run_id
        for attempt in attempts
    ) == ("JOB-1", "JOB-2")


def test_task_execution_result_validates_external_run_refs() -> None:
    try:
        TaskExecutionResult(external_runs=(object(),))  # type: ignore[arg-type]
    except TypeError as exc:
        assert "external_runs" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("invalid external run evidence must be rejected")



class UnconfirmedCancellationExecutor:
    """Cancellation adapter that exposes the remote run it could not stop."""

    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    @property
    def descriptor(self) -> ExecutorDescriptor:
        return ExecutorDescriptor(
            executor_id="inline",
            display_name="LOT-09 cancellation evidence executor",
            executor_version="1",
            supported_workload_kinds=("python_callable",),
            cancellation_capability=CancellationCapability.BEST_EFFORT,
        )

    def execute(self, request: TaskExecutionRequest) -> TaskExecutionResult:
        self.started.set()
        self.release.wait(timeout=5)
        return TaskExecutionResult(output="eventually-finished")

    def cancel(self, request: TaskCancellationRequest) -> TaskCancellationResult:
        return TaskCancellationResult(
            status=CancellationStatus.UNCONFIRMED,
            attempt_id=request.attempt_id,
            reason="remote_stop_not_confirmed",
            external_runs=(
                ExternalRunRef(
                    provider="remote-test",
                    kind="job",
                    external_run_id="JOB-CANCEL-1",
                    status_locator="memory://remote/JOB-CANCEL-1",
                ),
            ),
        )


def test_unconfirmed_cancellation_persists_external_identity_for_reconciliation() -> None:
    store = InMemoryMetadataStore()
    executor = UnconfirmedCancellationExecutor()
    runtime = WorkflowRuntime(executor=executor, metadata=store)
    results = []

    thread = Thread(target=lambda: results.append(runtime.run(_workflow())))
    thread.start()
    assert executor.started.wait(timeout=5)

    run_id = store.list_workflow_runs()[0].run_id
    cancellation = runtime.cancel(run_id)

    assert cancellation.status is CancellationStatus.UNCONFIRMED
    task_run = store.list_task_runs(run_id)[0]
    attempt = store.list_task_attempts(task_run.task_run_id)[0]
    refs = store.list_external_run_refs(attempt.attempt_id)

    assert store.get_workflow_run(run_id).status is WorkflowRunStatus.UNKNOWN_OUTCOME
    assert store.get_task_run(task_run.task_run_id).status is TaskRunStatus.UNKNOWN_OUTCOME
    assert store.get_task_attempt(attempt.attempt_id).status is (
        TaskAttemptStatus.CANCELLATION_UNCONFIRMED
    )
    assert len(refs) == 1
    assert refs[0].external_run_id == "JOB-CANCEL-1"

    executor.release.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert results[0].status is WorkflowRunStatus.SUCCEEDED
