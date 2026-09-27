"""M49 unit coverage for vendor-neutral observability interoperability."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Self

from pyworkflowkit.domain.enums import RuntimeEventType
from pyworkflowkit.domain.ids import RuntimeEventId, TaskId, TaskRunId, WorkflowRunId
from pyworkflowkit.domain.runtime import RuntimeEvent
from pyworkflowkit.integrations.telemetry import (
    OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION,
    OpenTelemetryBackend,
    RuntimeTelemetryProjector,
    RuntimeTelemetrySink,
    TelemetryEvent,
    TelemetryMetric,
    TelemetryMetricKind,
)

NOW = datetime(2026, 9, 27, 9, 0, tzinfo=UTC)


def _event(
    event_type: RuntimeEventType,
    *,
    sequence: int,
    occurred_at: datetime | None = None,
    task_run_id: str | None = None,
    task_id: str | None = None,
    attempt_number: int | None = None,
    payload: dict[str, object] | None = None,
) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=RuntimeEventId(f"event-{sequence}"),
        event_type=event_type,
        run_id=WorkflowRunId("run-1"),
        occurred_at=occurred_at or NOW,
        event_sequence=sequence,
        task_run_id=TaskRunId(task_run_id) if task_run_id is not None else None,
        task_id=TaskId(task_id) if task_id is not None else None,
        attempt_number=attempt_number,
        payload=payload or {},
    )


def test_observability_interoperability_contract_version_is_v1() -> None:
    assert OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION == "1"


def test_projector_preserves_domain_correlation_without_using_ids_as_metric_labels() -> None:
    projector = RuntimeTelemetryProjector()
    projection = projector.project(
        _event(
            RuntimeEventType.TASK_STARTED,
            sequence=2,
            task_run_id="task-run-1",
            task_id="fetch",
            attempt_number=1,
        )
    )

    correlation = projection.event.correlation.attributes()
    assert correlation["pyworkflowkit.event_id"] == "event-2"
    assert correlation["pyworkflowkit.run_id"] == "run-1"
    assert correlation["pyworkflowkit.task_run_id"] == "task-run-1"
    assert correlation["pyworkflowkit.task_id"] == "fetch"
    assert correlation["pyworkflowkit.attempt_number"] == 1

    for metric in projection.metrics:
        assert "pyworkflowkit.run_id" not in metric.attributes
        assert "pyworkflowkit.task_run_id" not in metric.attributes
        assert "pyworkflowkit.event_id" not in metric.attributes


def test_projector_generates_generic_workflow_and_task_duration_metrics() -> None:
    projector = RuntimeTelemetryProjector()

    projector.project(_event(RuntimeEventType.WORKFLOW_STARTED, sequence=1))
    projector.project(
        _event(
            RuntimeEventType.TASK_STARTED,
            sequence=2,
            occurred_at=NOW + timedelta(seconds=2),
            task_run_id="task-run-1",
            task_id="fetch",
            attempt_number=1,
        )
    )
    task_done = projector.project(
        _event(
            RuntimeEventType.TASK_SUCCEEDED,
            sequence=3,
            occurred_at=NOW + timedelta(seconds=5),
            task_run_id="task-run-1",
            task_id="fetch",
            attempt_number=1,
        )
    )
    workflow_done = projector.project(
        _event(
            RuntimeEventType.WORKFLOW_SUCCEEDED,
            sequence=4,
            occurred_at=NOW + timedelta(seconds=8),
        )
    )

    task_metrics = {metric.name: metric for metric in task_done.metrics}
    workflow_metrics = {metric.name: metric for metric in workflow_done.metrics}

    assert task_metrics["pyworkflowkit.task.completed"].attributes["outcome"] == "succeeded"
    assert task_metrics["pyworkflowkit.task.duration"].value == 3.0
    assert task_metrics["pyworkflowkit.task.duration"].unit == "s"
    assert workflow_metrics["pyworkflowkit.workflow.completed"].attributes["outcome"] == (
        "succeeded"
    )
    assert workflow_metrics["pyworkflowkit.workflow.duration"].value == 8.0


def test_projector_records_retry_counter_without_business_metrics() -> None:
    projector = RuntimeTelemetryProjector()
    projection = projector.project(
        _event(
            RuntimeEventType.TASK_RETRYING,
            sequence=3,
            task_run_id="task-run-1",
            task_id="fetch",
            attempt_number=1,
        )
    )

    names = {metric.name for metric in projection.metrics}
    assert "pyworkflowkit.runtime.events" in names
    assert "pyworkflowkit.task.retries" in names
    assert all("rows" not in name for name in names)
    assert all("revenue" not in name for name in names)


def test_projector_redacts_sensitive_payload_even_when_used_directly() -> None:
    projector = RuntimeTelemetryProjector()
    projection = projector.project(
        _event(
            RuntimeEventType.TASK_STARTED,
            sequence=1,
            payload={
                "api_token": "secret",
                "nested": {"password": "hidden", "safe": 42},
            },
        )
    )

    assert projection.event.payload == {
        "api_token": "<redacted>",
        "nested": {"password": "<redacted>", "safe": 42},
    }


@dataclass
class RecordingBackend:
    name: str = "recording"
    events: list[TelemetryEvent] = field(default_factory=list)
    metrics: list[TelemetryMetric] = field(default_factory=list)

    def emit_event(self, event: TelemetryEvent) -> None:
        self.events.append(event)

    def record_metric(self, metric: TelemetryMetric) -> None:
        self.metrics.append(metric)


def test_runtime_telemetry_sink_adapts_backend_to_runtime_event_sink() -> None:
    backend = RecordingBackend()
    sink = RuntimeTelemetrySink(backend)

    sink.emit(_event(RuntimeEventType.WORKFLOW_STARTED, sequence=1))

    assert sink.name == "telemetry:recording"
    assert backend.events[0].name == "pyworkflowkit.runtime.workflow_started"
    assert any(metric.name == "pyworkflowkit.workflow.started" for metric in backend.metrics)


@dataclass
class FakeSpan:
    attributes: dict[str, object] = field(default_factory=dict)
    events: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        del exc_type, exc_value, traceback

    def set_attribute(self, key: str, value: object) -> object:
        self.attributes[key] = value
        return self

    def add_event(
        self,
        name: str,
        attributes: dict[str, object] | None = None,
    ) -> object:
        self.events.append((name, dict(attributes or {})))
        return self


@dataclass
class FakeTracer:
    spans: list[FakeSpan] = field(default_factory=list)
    names: list[str] = field(default_factory=list)

    def start_as_current_span(self, name: str) -> FakeSpan:
        span = FakeSpan()
        self.names.append(name)
        self.spans.append(span)
        return span


@dataclass
class FakeCounter:
    observations: list[tuple[float, dict[str, object]]] = field(default_factory=list)

    def add(self, amount: int | float, attributes: dict[str, object] | None = None) -> object:
        self.observations.append((float(amount), dict(attributes or {})))
        return self


@dataclass
class FakeHistogram:
    observations: list[tuple[float, dict[str, object]]] = field(default_factory=list)

    def record(
        self,
        amount: int | float,
        attributes: dict[str, object] | None = None,
    ) -> object:
        self.observations.append((float(amount), dict(attributes or {})))
        return self


@dataclass
class FakeMeter:
    counters: dict[str, FakeCounter] = field(default_factory=dict)
    histograms: dict[str, FakeHistogram] = field(default_factory=dict)

    def create_counter(self, name: str, *, unit: str = "") -> FakeCounter:
        del unit
        counter = FakeCounter()
        self.counters[name] = counter
        return counter

    def create_histogram(self, name: str, *, unit: str = "") -> FakeHistogram:
        del unit
        histogram = FakeHistogram()
        self.histograms[name] = histogram
        return histogram


def test_opentelemetry_adapter_uses_injected_api_without_runtime_dependency() -> None:
    tracer = FakeTracer()
    meter = FakeMeter()
    backend = OpenTelemetryBackend(tracer=tracer, meter=meter)

    projector = RuntimeTelemetryProjector()
    projection = projector.project(
        _event(
            RuntimeEventType.TASK_STARTED,
            sequence=2,
            task_run_id="task-run-1",
            task_id="fetch",
            payload={"safe": "value"},
        )
    )

    backend.emit_event(projection.event)
    for metric in projection.metrics:
        backend.record_metric(metric)

    assert tracer.names == ["pyworkflowkit.runtime.task_started"]
    span = tracer.spans[0]
    assert span.attributes["pyworkflowkit.run_id"] == "run-1"
    assert span.attributes["pyworkflowkit.task_run_id"] == "task-run-1"
    assert span.events[0][1]["pyworkflowkit.payload_json"] == '{"safe":"value"}'
    assert "pyworkflowkit.runtime.events" in meter.counters
    assert "pyworkflowkit.task.started" in meter.counters


def test_metric_value_requires_finite_number() -> None:
    try:
        TelemetryMetric(
            name="invalid",
            kind=TelemetryMetricKind.HISTOGRAM,
            value=float("inf"),
            occurred_at=NOW,
        )
    except ValueError as exc:
        assert "finite" in str(exc)
    else:
        raise AssertionError("expected non-finite metric rejection")
