"""M49 reference acceptance for observability interoperability."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pyworkflowkit import RetryPolicy, WorkflowRuntime, task, workflow
from pyworkflowkit.application.observability_plugins import ObservabilityDispatcher
from pyworkflowkit.domain.enums import RuntimeEventType, WorkflowRunStatus
from pyworkflowkit.domain.ids import RuntimeEventId, WorkflowRunId
from pyworkflowkit.domain.runtime import RuntimeEvent
from pyworkflowkit.integrations import (
    OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION,
    RuntimeTelemetrySink,
    TelemetryEvent,
    TelemetryMetric,
)


@dataclass
class RecordingBackend:
    name: str = "reference"
    events: list[TelemetryEvent] = field(default_factory=list)
    metrics: list[TelemetryMetric] = field(default_factory=list)

    def emit_event(self, event: TelemetryEvent) -> None:
        self.events.append(event)

    def record_metric(self, metric: TelemetryMetric) -> None:
        self.metrics.append(metric)


class BrokenBackend:
    name = "broken"

    def emit_event(self, event: TelemetryEvent) -> None:
        del event
        raise RuntimeError("backend unavailable: token=do-not-leak")

    def record_metric(self, metric: TelemetryMetric) -> None:
        del metric
        raise RuntimeError("backend unavailable")


def test_runtime_facade_projects_committed_events_and_generic_metrics() -> None:
    backend = RecordingBackend()
    runtime = WorkflowRuntime()
    runtime.register_event_sink(RuntimeTelemetrySink(backend))

    attempts = 0

    @task(
        id="work",
        retry_policy=RetryPolicy(
            max_attempts=2,
            retryable_error_categories=frozenset({"RuntimeError"}),
        ),
    )
    def work() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary")
        return "ok"

    @workflow(id="reference.m49", version="1")
    def definition():
        return (work,)

    runtime.register(work.handler_ref, work.handler)
    workflow_definition = definition.build()
    run = runtime.run(workflow_definition)
    persisted = runtime.events(run.run_id)

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert attempts == 2
    assert OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION == "1"
    assert len(backend.events) == len(persisted)
    assert tuple(event.correlation.event_id for event in backend.events) == tuple(
        str(event.event_id) for event in persisted
    )
    assert tuple(event.correlation.run_id for event in backend.events) == tuple(
        str(run.run_id) for _ in persisted
    )

    metric_names = {metric.name for metric in backend.metrics}
    assert "pyworkflowkit.runtime.events" in metric_names
    assert "pyworkflowkit.workflow.started" in metric_names
    assert "pyworkflowkit.workflow.completed" in metric_names
    assert "pyworkflowkit.workflow.duration" in metric_names
    assert "pyworkflowkit.task.started" in metric_names
    assert "pyworkflowkit.task.retries" in metric_names
    assert "pyworkflowkit.task.completed" in metric_names
    assert "pyworkflowkit.task.duration" in metric_names

    for metric in backend.metrics:
        assert "pyworkflowkit.run_id" not in metric.attributes
        assert "pyworkflowkit.task_run_id" not in metric.attributes


def test_telemetry_backend_failure_is_isolated_from_workflow_outcome() -> None:
    recording = RecordingBackend()
    runtime = WorkflowRuntime()
    runtime.register_event_sink(RuntimeTelemetrySink(BrokenBackend()))
    runtime.register_event_sink(RuntimeTelemetrySink(recording))

    @task(id="work")
    def work() -> str:
        return "ok"

    @workflow(id="reference.m49.failure-isolation", version="1")
    def definition():
        return (work,)

    runtime.register(work.handler_ref, work.handler)
    run = runtime.run(definition.build())

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert recording.events
    assert runtime.observability_failures
    assert {failure.sink_name for failure in runtime.observability_failures} == {
        "telemetry:broken"
    }
    assert all(
        failure.error_message == "<redacted>"
        for failure in runtime.observability_failures
    )


def test_telemetry_projection_redacts_committed_event_payload() -> None:
    backend = RecordingBackend()
    dispatcher = ObservabilityDispatcher((RuntimeTelemetrySink(backend),))
    event = RuntimeEvent(
        event_id=RuntimeEventId("event-1"),
        event_type=RuntimeEventType.TASK_STARTED,
        run_id=WorkflowRunId("run-1"),
        occurred_at=datetime.now(UTC),
        event_sequence=1,
        payload={
            "authorization": "Bearer secret",
            "nested": {"private_key": "hidden", "safe": "visible"},
        },
    )

    dispatcher.publish(event)

    assert backend.events[0].payload == {
        "authorization": "<redacted>",
        "nested": {"private_key": "<redacted>", "safe": "visible"},
    }


def test_m49_does_not_change_durable_runtime_event_vocabulary() -> None:
    assert {event.value for event in RuntimeEventType} == {
        "WORKFLOW_STARTED",
        "WORKFLOW_SUCCEEDED",
        "WORKFLOW_FAILED",
        "WORKFLOW_CANCELLED",
        "TASK_READY",
        "TASK_STARTED",
        "TASK_RETRYING",
        "TASK_SUCCEEDED",
        "TASK_FAILED",
        "TASK_SKIPPED",
    }
