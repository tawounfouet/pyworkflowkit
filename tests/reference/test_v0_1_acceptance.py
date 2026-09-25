"""V0.1 reference workflows and end-to-end acceptance scenarios."""

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.manifest import REDACTED_VALUE, RunManifestBuilder
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    RuntimeEventType,
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import (
    ArtifactId,
    ExternalRunRefId,
    RuntimeEventId,
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
from pyworkflowkit.errors import CycleDetectedError, TaskExecutionError
from pyworkflowkit.ports.executor import RunContext

NOW = datetime(2026, 9, 25, 23, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class NoopSleeper:
    def sleep(self, seconds: float) -> None:
        del seconds


class DeterministicIds:
    def new_workflow_run_id(self) -> WorkflowRunId:
        return WorkflowRunId("run-1")

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

    def new_runtime_event_id(
        self,
        *,
        run_id: WorkflowRunId,
        event_sequence: int,
    ) -> RuntimeEventId:
        return RuntimeEventId(f"{run_id}:event-{event_sequence}")


def task(
    task_id: str,
    *depends_on: str,
    retry_policy: RetryPolicy | None = None,
) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(task_id),
        handler_ref=f"handlers:{task_id}",
        depends_on=tuple(TaskId(value) for value in depends_on),
        retry_policy=retry_policy or RetryPolicy(),
    )


def workflow(
    *tasks: TaskDefinition,
    parameters: tuple[WorkflowParameter, ...] = (),
) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("reference"),
        version="1",
        tasks=tasks,
        parameters=parameters,
    )


def runtime(
    handlers: Mapping[str, object],
) -> tuple[Runner, MemoryMetadataStore]:
    store = MemoryMetadataStore()
    registry = HandlerRegistry()
    for handler_ref, handler in handlers.items():
        registry.register(handler_ref, handler)  # type: ignore[arg-type]

    return (
        Runner(
            metadata_store=store,
            handler_registry=registry,
            executor=LocalExecutor(),
            clock=FixedClock(),
            id_factory=DeterministicIds(),
            sleeper=NoopSleeper(),
        ),
        store,
    )


def test_rf001_single_task_success() -> None:
    definition = workflow(task("A"))
    runner, store = runtime({"handlers:A": lambda: "ok"})

    run = runner.run(definition)

    assert run.status is WorkflowRunStatus.SUCCEEDED
    task_run = store.list_task_runs(run.run_id)[0]
    assert task_run.status is TaskRunStatus.SUCCEEDED
    assert tuple(event.event_type for event in store.list_events(run.run_id)) == (
        RuntimeEventType.WORKFLOW_STARTED,
        RuntimeEventType.TASK_READY,
        RuntimeEventType.TASK_STARTED,
        RuntimeEventType.TASK_SUCCEEDED,
        RuntimeEventType.WORKFLOW_SUCCEEDED,
    )


def test_rf002_linear_dependency_outputs() -> None:
    observed: list[str] = []

    def fetch() -> int:
        observed.append("A")
        return 21

    def transform(context: RunContext) -> int:
        observed.append("B")
        return int(context.dependency_outputs[TaskId("A")]) * 2

    def publish(context: RunContext) -> int:
        observed.append("C")
        return int(context.dependency_outputs[TaskId("B")])

    definition = workflow(
        task("C", "B"),
        task("B", "A"),
        task("A"),
    )
    runner, _ = runtime(
        {
            "handlers:A": fetch,
            "handlers:B": transform,
            "handlers:C": publish,
        }
    )

    run = runner.run(definition)

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert observed == ["A", "B", "C"]


def test_rf003_diamond_is_deterministic_in_sequential_v0_1() -> None:
    calls: list[str] = []

    def handler(name: str):
        def execute() -> str:
            calls.append(name)
            return name

        return execute

    def join(context: RunContext) -> tuple[object, object]:
        calls.append("D")
        return (
            context.dependency_outputs[TaskId("B")],
            context.dependency_outputs[TaskId("C")],
        )

    definition = workflow(
        task("D", "B", "C"),
        task("C", "A"),
        task("B", "A"),
        task("A"),
    )
    runner, _ = runtime(
        {
            "handlers:A": handler("A"),
            "handlers:B": handler("B"),
            "handlers:C": handler("C"),
            "handlers:D": join,
        }
    )

    runner.run(definition)

    assert calls == ["A", "B", "C", "D"]


def test_rf004_retry_then_success_uses_same_task_run() -> None:
    calls = 0

    def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    definition = workflow(
        task("A", retry_policy=RetryPolicy(max_attempts=2)),
    )
    runner, store = runtime({"handlers:A": flaky})

    run = runner.run(definition)
    task_run = store.list_task_runs(run.run_id)[0]
    attempts = store.list_task_attempts(task_run.task_run_id)

    assert tuple(attempt.status for attempt in attempts) == (
        TaskAttemptStatus.FAILED,
        TaskAttemptStatus.SUCCEEDED,
    )
    assert len({attempt.task_run_id for attempt in attempts}) == 1
    assert tuple(event.event_type for event in store.list_events(run.run_id)) == (
        RuntimeEventType.WORKFLOW_STARTED,
        RuntimeEventType.TASK_READY,
        RuntimeEventType.TASK_STARTED,
        RuntimeEventType.TASK_RETRYING,
        RuntimeEventType.TASK_SUCCEEDED,
        RuntimeEventType.WORKFLOW_SUCCEEDED,
    )


def test_rf005_retry_exhaustion_and_fail_fast_propagation() -> None:
    def failing() -> None:
        raise TimeoutError("still failing")

    definition = workflow(
        task("D", "B"),
        task("C"),
        task("B", "A"),
        task("A", retry_policy=RetryPolicy(max_attempts=2)),
    )
    runner, store = runtime(
        {
            "handlers:A": failing,
            "handlers:B": lambda: None,
            "handlers:C": lambda: None,
            "handlers:D": lambda: None,
        }
    )

    with pytest.raises(TaskExecutionError):
        runner.run(definition)

    run = store.get_workflow_run(WorkflowRunId("run-1"))
    runs = {item.task_id: item for item in store.list_task_runs(run.run_id)}

    assert run.status is WorkflowRunStatus.FAILED
    assert runs[TaskId("A")].status is TaskRunStatus.FAILED
    assert runs[TaskId("B")].skip_reason is SkipReason.DEPENDENCY_FAILED
    assert runs[TaskId("D")].skip_reason is SkipReason.DEPENDENCY_FAILED
    assert runs[TaskId("C")].skip_reason is SkipReason.FAIL_FAST_ABORT


def test_rf006_manifest_is_portable_deterministic_and_redacts_sensitive_values() -> None:
    artifact = ArtifactReference(
        artifact_id=ArtifactId("artifact-1"),
        name="output.csv",
        uri="file:///tmp/output.csv",
        metadata={"rows": 10},
    )
    external_ref = ExternalRunRef(
        external_ref_id=ExternalRunRefId("external-1"),
        provider="pyingestkit",
        external_run_id="job-1",
    )

    definition = workflow(
        task("A"),
        parameters=(
            WorkflowParameter(name="source"),
            WorkflowParameter(name="token", sensitive=True),
        ),
    )
    runner, store = runtime(
        {
            "handlers:A": lambda: TaskResult(
                output="ok",
                artifacts=(artifact,),
                external_refs=(external_ref,),
            )
        }
    )

    run = runner.run(
        definition,
        parameters={"source": "input.csv", "token": "secret"},
    )
    builder = RunManifestBuilder(metadata_store=store)

    first = builder.build(workflow=definition, run_id=run.run_id)
    second = builder.build(workflow=definition, run_id=run.run_id)

    assert first == second
    assert first.parameters["token"] == REDACTED_VALUE
    assert first.tasks[0].artifacts[0].artifact_id == "artifact-1"
    assert first.tasks[0].external_refs[0].external_run_id == "job-1"


def test_rf007_cycle_is_rejected_before_runtime_metadata_exists() -> None:
    definition = workflow(
        task("A", "C"),
        task("B", "A"),
        task("C", "B"),
    )
    runner, store = runtime(
        {
            "handlers:A": lambda: None,
            "handlers:B": lambda: None,
            "handlers:C": lambda: None,
        }
    )

    with pytest.raises(CycleDetectedError):
        runner.run(definition)

    assert store.list_task_runs(WorkflowRunId("run-1")) == ()
    assert store.list_events(WorkflowRunId("run-1")) == ()
