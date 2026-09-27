"""Strict external-consumer typing fixture for PyWorkflowKit RQ-03."""

from __future__ import annotations

from collections.abc import Sequence
from types import TracebackType
from typing import Self, assert_type

from pyworkflowkit import TaskHandle, WorkflowBuilder, task, workflow
from pyworkflowkit.control_plane import ControlPlaneProvider, WorkflowRuntimeProvider
from pyworkflowkit.ecosystem import (
    ArtifactReference,
    CancellationCapability,
    Executor,
    ExecutorCapabilities,
    ExternalRunRef,
    ExternalWorkload,
    ExternalWorkloadResult,
    MetadataStore,
    PluginType,
    RunContext,
    RuntimeEvent,
    RuntimeEventSink,
    TaskAttempt,
    TaskDefinition,
    TaskHandler,
    TaskResult,
    TaskRun,
    TaskRunId,
    TimeoutCapability,
    UnitOfWork,
    WorkflowRun,
    WorkflowRunId,
    plugin_registration,
)
from pyworkflowkit.integrations import TelemetryBackend, TelemetryEvent, TelemetryMetric


@task(id="zero")
def zero_task() -> int:
    return 1


@task(id="context", depends_on=(zero_task,))
def context_task(context: RunContext) -> TaskResult:
    return TaskResult(output=context.attempt_number)


@workflow(id="typing.consumer", version="1")
def consumer_workflow() -> tuple[TaskHandle, ...]:
    return (zero_task, context_task)


assert_type(consumer_workflow, WorkflowBuilder)


class ConsumerExecutor:
    @property
    def key(self) -> str:
        return "consumer"

    @property
    def capabilities(self) -> ExecutorCapabilities:
        return ExecutorCapabilities(
            supports_parallelism=True,
            timeout=TimeoutCapability.SOFT,
            cancellation=CancellationCapability.COOPERATIVE,
            max_concurrency=2,
        )

    def execute(
        self,
        *,
        task: TaskDefinition,
        handler: TaskHandler,
        context: RunContext,
    ) -> TaskResult:
        del task, handler, context
        return TaskResult(output=None)


executor: Executor = ConsumerExecutor()


class ConsumerUnitOfWork:
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        del exc_type, exc_value, traceback
        return None

    def add_workflow_run(self, run: WorkflowRun) -> None:
        del run

    def save_workflow_run(self, run: WorkflowRun) -> None:
        del run

    def add_task_run(self, task_run: TaskRun) -> None:
        del task_run

    def save_task_run(self, task_run: TaskRun) -> None:
        del task_run

    def add_task_attempt(self, attempt: TaskAttempt) -> None:
        del attempt

    def save_task_attempt(self, attempt: TaskAttempt) -> None:
        del attempt

    def add_event(self, event: RuntimeEvent) -> None:
        del event

    def add_task_output_checkpoint(
        self,
        *,
        task_run_id: TaskRunId,
        output: object,
    ) -> None:
        del task_run_id, output

    def add_artifact(
        self,
        *,
        task_run_id: TaskRunId,
        artifact: ArtifactReference,
    ) -> None:
        del task_run_id, artifact

    def add_external_run_ref(
        self,
        *,
        task_run_id: TaskRunId,
        external_ref: ExternalRunRef,
    ) -> None:
        del task_run_id, external_ref

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


unit_of_work: UnitOfWork = ConsumerUnitOfWork()


class ConsumerMetadataStore:
    def unit_of_work(self) -> UnitOfWork:
        return ConsumerUnitOfWork()

    def get_workflow_run(self, run_id: WorkflowRunId) -> WorkflowRun:
        del run_id
        raise NotImplementedError

    def get_task_run(self, task_run_id: TaskRunId) -> TaskRun:
        del task_run_id
        raise NotImplementedError

    def list_workflow_runs(self) -> Sequence[WorkflowRun]:
        return ()

    def list_task_runs(self, run_id: WorkflowRunId) -> Sequence[TaskRun]:
        del run_id
        return ()

    def list_task_attempts(self, task_run_id: TaskRunId) -> Sequence[TaskAttempt]:
        del task_run_id
        return ()

    def list_events(self, run_id: WorkflowRunId) -> Sequence[RuntimeEvent]:
        del run_id
        return ()

    def get_task_output_checkpoint(self, task_run_id: TaskRunId) -> object:
        del task_run_id
        raise NotImplementedError

    def list_artifacts(self, task_run_id: TaskRunId) -> Sequence[ArtifactReference]:
        del task_run_id
        return ()

    def list_external_run_refs(self, task_run_id: TaskRunId) -> Sequence[ExternalRunRef]:
        del task_run_id
        return ()


metadata_store: MetadataStore = ConsumerMetadataStore()


class ConsumerEventSink:
    @property
    def name(self) -> str:
        return "consumer"

    def emit(self, event: RuntimeEvent) -> None:
        del event


event_sink: RuntimeEventSink = ConsumerEventSink()


class ConsumerWorkload:
    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        return ExternalWorkloadResult(
            external_run_id=f"consumer-{context.task_run_id}",
            succeeded=True,
        )


workload: ExternalWorkload = ConsumerWorkload()
registration = plugin_registration(
    name="consumer-workload",
    plugin_type=PluginType.WORKLOAD,
    factory=ConsumerWorkload,
)
assert_type(registration.create(), ConsumerWorkload)


class ConsumerTelemetryBackend:
    @property
    def name(self) -> str:
        return "consumer"

    def emit_event(self, event: TelemetryEvent) -> None:
        del event

    def record_metric(self, metric: TelemetryMetric) -> None:
        del metric


telemetry_backend: TelemetryBackend = ConsumerTelemetryBackend()


def accept_control_plane(provider: ControlPlaneProvider) -> None:
    del provider


def prove_builtin_provider(value: WorkflowRuntimeProvider) -> None:
    accept_control_plane(value)
