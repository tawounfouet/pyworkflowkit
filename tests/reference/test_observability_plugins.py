"""M35 reference acceptance for committed-event observability plugins."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.observability_plugins import ObservabilityDispatcher
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import RuntimeEventType, WorkflowRunStatus
from pyworkflowkit.domain.ids import (
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import RuntimeEvent
from pyworkflowkit.ports.executor import RunContext

NOW = datetime(2026, 9, 26, 20, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class NoopSleeper:
    def sleep(self, seconds: float) -> None:
        del seconds


class DeterministicIds:
    def new_workflow_run_id(self) -> WorkflowRunId:
        return WorkflowRunId("run-observability")

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


@dataclass
class RecordingSink:
    name: str = "recording"
    events: list[RuntimeEvent] = field(default_factory=list)

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)


@dataclass
class PersistedProbeSink:
    store: MemoryMetadataStore
    name: str = "persisted-probe"
    events: list[RuntimeEvent] = field(default_factory=list)

    def emit(self, event: RuntimeEvent) -> None:
        persisted_ids = {persisted.event_id for persisted in self.store.list_events(event.run_id)}
        assert event.event_id in persisted_ids
        self.events.append(event)


@dataclass
class BrokenSink:
    name: str = "broken"

    def emit(self, event: RuntimeEvent) -> None:
        del event
        raise RuntimeError("telemetry backend unavailable")


def _workflow(*tasks: TaskDefinition) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("reference.observability"),
        version="1",
        tasks=tasks,
    )


def _task(name: str, *, executor_key: str = "local") -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(name),
        handler_ref=f"handlers:{name}",
        executor_key=executor_key,
    )


def test_runner_publishes_only_committed_events_in_durable_sequence_order() -> None:
    store = MemoryMetadataStore()
    registry = HandlerRegistry()
    registry.register("handlers:one", lambda: "ok")
    sink = PersistedProbeSink(store)
    dispatcher = ObservabilityDispatcher((sink,))
    runner = Runner(
        metadata_store=store,
        handler_registry=registry,
        executor=LocalExecutor(),
        clock=FixedClock(),
        id_factory=DeterministicIds(),
        sleeper=NoopSleeper(),
        observability=dispatcher,
    )

    run = runner.run(_workflow(_task("one")))
    persisted = tuple(store.list_events(run.run_id))

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert tuple(event.event_id for event in sink.events) == tuple(
        event.event_id for event in persisted
    )
    assert tuple(event.event_sequence for event in sink.events) == (1, 2, 3, 4, 5)
    assert tuple(event.event_type for event in sink.events) == (
        RuntimeEventType.WORKFLOW_STARTED,
        RuntimeEventType.TASK_READY,
        RuntimeEventType.TASK_STARTED,
        RuntimeEventType.TASK_SUCCEEDED,
        RuntimeEventType.WORKFLOW_SUCCEEDED,
    )


def test_observability_backend_failure_does_not_change_workflow_outcome() -> None:
    store = MemoryMetadataStore()
    registry = HandlerRegistry()
    registry.register("handlers:one", lambda: "ok")
    recording = RecordingSink()
    dispatcher = ObservabilityDispatcher((BrokenSink(), recording))
    runner = Runner(
        metadata_store=store,
        handler_registry=registry,
        executor=LocalExecutor(),
        clock=FixedClock(),
        id_factory=DeterministicIds(),
        sleeper=NoopSleeper(),
        observability=dispatcher,
    )

    run = runner.run(_workflow(_task("one")))

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert len(recording.events) == 5
    assert len(dispatcher.failures) == 5


def test_concurrent_runner_uses_same_committed_event_dispatch_contract() -> None:
    store = MemoryMetadataStore()
    registry = HandlerRegistry()

    def contextual(context: RunContext) -> str:
        return str(context.task_id)

    registry.register("handlers:a", contextual)
    registry.register("handlers:b", contextual)
    sink = PersistedProbeSink(store)
    dispatcher = ObservabilityDispatcher((sink,))
    executor = ThreadExecutor(max_workers=2)
    runner = ConcurrentRunner(
        metadata_store=store,
        handler_registry=registry,
        executor=executor,
        clock=FixedClock(),
        id_factory=DeterministicIds(),
        sleeper=NoopSleeper(),
        global_limit=2,
        observability=dispatcher,
    )

    try:
        run = runner.run(
            _workflow(
                _task("a", executor_key="thread"),
                _task("b", executor_key="thread"),
            )
        )
        persisted = tuple(store.list_events(run.run_id))

        assert run.status is WorkflowRunStatus.SUCCEEDED
        assert tuple(event.event_id for event in sink.events) == tuple(
            event.event_id for event in persisted
        )
    finally:
        executor.shutdown()


def test_workflow_runtime_facade_can_register_event_sink() -> None:
    runtime = WorkflowRuntime()
    sink = RecordingSink()
    runtime.register_event_sink(sink)
    runtime.register("handlers:one", lambda: "ok")

    run = runtime.run(_workflow(_task("one")))

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert tuple(event.event_id for event in sink.events) == tuple(
        event.event_id for event in runtime.events(run.run_id)
    )
    assert runtime.observability_failures == ()
