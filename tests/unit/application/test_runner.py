"""Tests for the first sequential executable Runner vertical slice."""

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import (
    ArtifactId,
    ExternalRunRefId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.values import (
    ArtifactReference,
    ExternalRunRef,
    RetryPolicy,
    TaskResult,
    WorkflowParameter,
)
from pyworkflowkit.errors import (
    ExecutorNotFoundError,
    HandlerNotFoundError,
    InvalidHandlerError,
    InvalidWorkflowParametersError,
    MetadataNotFoundError,
    TaskExecutionError,
    UnknownDependencyError,
)
from pyworkflowkit.ports.executor import RunContext
from pyworkflowkit.ports.runtime import Clock, RuntimeIdFactory

NOW = datetime(2026, 9, 25, 19, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class DeterministicIdFactory:
    def new_workflow_run_id(self) -> WorkflowRunId:
        return WorkflowRunId("workflow-run-1")

    def new_task_run_id(
        self,
        *,
        run_id: WorkflowRunId,
        task_id: TaskId,
    ) -> TaskRunId:
        return TaskRunId(f"{run_id}:{task_id}")

    def new_task_attempt_id(
        self,
        *,
        task_run_id: TaskRunId,
        attempt_number: int,
    ) -> TaskAttemptId:
        return TaskAttemptId(f"{task_run_id}:attempt-{attempt_number}")


def make_task(
    task_id: str,
    *depends_on: str,
    handler_ref: str | None = None,
    executor_key: str = "local",
    retry_policy: RetryPolicy | None = None,
) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(task_id),
        handler_ref=handler_ref or f"handlers:{task_id}",
        depends_on=tuple(TaskId(value) for value in depends_on),
        executor_key=executor_key,
        retry_policy=retry_policy or RetryPolicy(),
    )


def make_workflow(
    *tasks: TaskDefinition,
    parameters: tuple[WorkflowParameter, ...] = (),
) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("workflow"),
        version="1",
        tasks=tasks,
        parameters=parameters,
    )


def make_runtime(
    workflow: WorkflowDefinition,
    handlers: Mapping[str, object],
) -> tuple[Runner, MemoryMetadataStore]:
    del workflow
    store = MemoryMetadataStore()
    registry = HandlerRegistry()
    for handler_ref, handler in handlers.items():
        registry.register(handler_ref, handler)  # type: ignore[arg-type]

    runner = Runner(
        metadata_store=store,
        handler_registry=registry,
        executor=LocalExecutor(),
        clock=FixedClock(),
        id_factory=DeterministicIdFactory(),
    )
    assert isinstance(FixedClock(), Clock)
    assert isinstance(DeterministicIdFactory(), RuntimeIdFactory)
    return runner, store


def test_runner_executes_single_task_to_success() -> None:
    workflow = make_workflow(make_task("A"))
    runner, store = make_runtime(
        workflow,
        {"handlers:A": lambda: "done"},
    )

    run = runner.run(workflow)

    assert run.status is WorkflowRunStatus.SUCCEEDED
    task_runs = store.list_task_runs(run.run_id)
    assert len(task_runs) == 1
    assert task_runs[0].status is TaskRunStatus.SUCCEEDED

    attempts = store.list_task_attempts(task_runs[0].task_run_id)
    assert len(attempts) == 1
    assert attempts[0].status is TaskAttemptStatus.SUCCEEDED


def test_runner_executes_linear_workflow_and_passes_dependency_output() -> None:
    calls: list[str] = []

    def fetch() -> int:
        calls.append("A")
        return 21

    def transform(context: RunContext) -> int:
        calls.append("B")
        return context.dependency_outputs[TaskId("A")] * 2  # type: ignore[operator]

    workflow = make_workflow(
        make_task("B", "A"),
        make_task("A"),
    )
    runner, store = make_runtime(
        workflow,
        {
            "handlers:A": fetch,
            "handlers:B": transform,
        },
    )

    run = runner.run(workflow)

    assert calls == ["A", "B"]
    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert {task.task_id: task.status for task in store.list_task_runs(run.run_id)} == {
        TaskId("A"): TaskRunStatus.SUCCEEDED,
        TaskId("B"): TaskRunStatus.SUCCEEDED,
    }


def test_runner_executes_diamond_in_deterministic_plan_order() -> None:
    calls: list[str] = []

    def record(name: str) -> object:
        def handler() -> str:
            calls.append(name)
            return name

        return handler

    def join(context: RunContext) -> tuple[object, object]:
        calls.append("D")
        return (
            context.dependency_outputs[TaskId("B")],
            context.dependency_outputs[TaskId("C")],
        )

    workflow = make_workflow(
        make_task("D", "B", "C"),
        make_task("C", "A"),
        make_task("B", "A"),
        make_task("A"),
    )
    runner, _ = make_runtime(
        workflow,
        {
            "handlers:A": record("A"),
            "handlers:B": record("B"),
            "handlers:C": record("C"),
            "handlers:D": join,
        },
    )

    run = runner.run(workflow)

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert calls == ["A", "B", "C", "D"]


def test_runner_resolves_required_and_optional_parameters() -> None:
    observed: dict[str, object] = {}

    def handler(context: RunContext) -> None:
        observed.update(context.workflow_parameters)

    workflow = make_workflow(
        make_task("A"),
        parameters=(
            WorkflowParameter(name="required"),
            WorkflowParameter(name="optional", required=False, default="fallback"),
        ),
    )
    runner, _ = make_runtime(workflow, {"handlers:A": handler})

    runner.run(workflow, parameters={"required": "provided"})

    assert observed == {
        "required": "provided",
        "optional": "fallback",
    }


def test_runner_rejects_missing_required_parameter_before_creating_run() -> None:
    workflow = make_workflow(
        make_task("A"),
        parameters=(WorkflowParameter(name="required"),),
    )
    runner, store = make_runtime(workflow, {"handlers:A": lambda: None})

    with pytest.raises(InvalidWorkflowParametersError, match="required"):
        runner.run(workflow)

    with pytest.raises(MetadataNotFoundError):
        store.get_workflow_run(WorkflowRunId("workflow-run-1"))


def test_runner_rejects_unknown_parameter_before_creating_run() -> None:
    workflow = make_workflow(make_task("A"))
    runner, _ = make_runtime(workflow, {"handlers:A": lambda: None})

    with pytest.raises(InvalidWorkflowParametersError, match="unknown"):
        runner.run(workflow, parameters={"other": 1})


def test_runner_rejects_invalid_dag_before_creating_run() -> None:
    workflow = make_workflow(make_task("B", "missing"))
    runner, store = make_runtime(workflow, {"handlers:B": lambda: None})

    with pytest.raises(UnknownDependencyError):
        runner.run(workflow)

    with pytest.raises(MetadataNotFoundError):
        store.get_workflow_run(WorkflowRunId("workflow-run-1"))


def test_runner_rejects_missing_handler_before_creating_run() -> None:
    workflow = make_workflow(make_task("A"))
    runner, store = make_runtime(workflow, {})

    with pytest.raises(HandlerNotFoundError):
        runner.run(workflow)

    with pytest.raises(MetadataNotFoundError):
        store.get_workflow_run(WorkflowRunId("workflow-run-1"))


def test_runner_rejects_missing_handler_ref_before_creating_run() -> None:
    workflow = make_workflow(
        TaskDefinition(
            task_id=TaskId("A"),
            handler_ref=None,
        )
    )
    runner, _ = make_runtime(workflow, {})

    with pytest.raises(InvalidHandlerError, match="handler_ref"):
        runner.run(workflow)


def test_runner_rejects_unavailable_executor_before_creating_run() -> None:
    workflow = make_workflow(make_task("A", executor_key="remote"))
    runner, _ = make_runtime(workflow, {"handlers:A": lambda: None})

    with pytest.raises(ExecutorNotFoundError) as exc_info:
        runner.run(workflow)

    assert exc_info.value.executor_key == "remote"


def test_runner_persists_artifacts_and_external_refs_from_successful_result() -> None:
    artifact = ArtifactReference(
        artifact_id=ArtifactId("artifact-1"),
        name="output.csv",
        uri="file:///tmp/output.csv",
    )
    external_ref = ExternalRunRef(
        external_ref_id=ExternalRunRefId("external-1"),
        provider="pyingestkit",
        external_run_id="job-1",
    )
    workflow = make_workflow(make_task("A"))
    runner, store = make_runtime(
        workflow,
        {
            "handlers:A": lambda: TaskResult(
                output="done",
                artifacts=(artifact,),
                external_refs=(external_ref,),
            )
        },
    )

    run = runner.run(workflow)
    task_run = store.list_task_runs(run.run_id)[0]

    assert store.list_artifacts(task_run.task_run_id) == (artifact,)
    assert store.list_external_run_refs(task_run.task_run_id) == (external_ref,)


def test_runner_persists_failure_and_reraises_execution_error() -> None:
    def failing() -> None:
        raise ValueError("boom")

    workflow = make_workflow(
        make_task("B", "A"),
        make_task("A"),
    )
    runner, store = make_runtime(
        workflow,
        {
            "handlers:A": failing,
            "handlers:B": lambda: None,
        },
    )

    with pytest.raises(TaskExecutionError) as exc_info:
        runner.run(workflow)

    assert exc_info.value.error_type == "ValueError"

    run = store.get_workflow_run(WorkflowRunId("workflow-run-1"))
    assert run.status is WorkflowRunStatus.FAILED

    runs = {task.task_id: task for task in store.list_task_runs(run.run_id)}
    assert runs[TaskId("A")].status is TaskRunStatus.FAILED
    assert runs[TaskId("B")].status is TaskRunStatus.PENDING

    attempts = store.list_task_attempts(runs[TaskId("A")].task_run_id)
    assert len(attempts) == 1
    assert attempts[0].status is TaskAttemptStatus.FAILED
    assert attempts[0].error_type == "ValueError"
    assert attempts[0].error_message == "boom"


def test_runner_does_not_apply_retry_policy_yet() -> None:
    calls = 0

    def failing() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("still failing")

    workflow = make_workflow(
        make_task(
            "A",
            retry_policy=RetryPolicy(max_attempts=3),
        )
    )
    runner, store = make_runtime(workflow, {"handlers:A": failing})

    with pytest.raises(TaskExecutionError):
        runner.run(workflow)

    task_run = store.list_task_runs(WorkflowRunId("workflow-run-1"))[0]
    assert calls == 1
    assert len(store.list_task_attempts(task_run.task_run_id)) == 1
