"""Unit tests for OpenTelemetryBridge and telemetry bridge discovery."""

from __future__ import annotations

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from pyworkflowkit.executors.subprocess import SubprocessExecutor
from pyworkflowkit.persistence.memory import InMemoryMetadataStore
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.identity import CorrelationId
from pyworkflowkit.runtime.telemetry import (
    OpenTelemetryBridge,
    TelemetryBridge,
    get_telemetry_bridge,
)
from pyworkflowkit.runtime.workflow import WorkflowRuntime


@pytest.fixture
def memory_exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def tracer_provider(memory_exporter: InMemorySpanExporter) -> TracerProvider:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory_exporter))
    return provider


@pytest.fixture
def bridge(tracer_provider: TracerProvider) -> OpenTelemetryBridge:
    tracer = tracer_provider.get_tracer("test_tracer")
    return OpenTelemetryBridge(tracer)


def test_opentelemetry_bridge_satisfies_protocol(bridge: OpenTelemetryBridge) -> None:
    assert isinstance(bridge, TelemetryBridge)


def test_start_workflow_span_attributes_and_status(
    bridge: OpenTelemetryBridge,
    memory_exporter: InMemorySpanExporter,
) -> None:
    correlation = CorrelationContext(
        correlation_id=CorrelationId.parse("C-test"),
        causation_id="cause-123",
    )
    with bridge.start_workflow_span(
        "OrderFulfillment", "wfr-123", correlation, workflow_version="2.1.0"
    ):
        pass

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert span.name == "workflow: OrderFulfillment"
    assert span.status.status_code == StatusCode.OK
    assert span.attributes["workflow.name"] == "OrderFulfillment"
    assert span.attributes["workflow.run_id"] == "wfr-123"
    assert span.attributes["workflow.version"] == "2.1.0"
    assert span.attributes["correlation.id"] == "C-test"
    assert span.attributes["correlation.causation_id"] == "cause-123"


def test_start_workflow_span_exception_recording(
    bridge: OpenTelemetryBridge,
    memory_exporter: InMemorySpanExporter,
) -> None:
    correlation = CorrelationContext()
    with (
        pytest.raises(ValueError, match="workflow failed"),
        bridge.start_workflow_span("FailingWorkflow", "wfr-err", correlation),
    ):
        raise ValueError("workflow failed")

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "workflow: FailingWorkflow"
    assert span.status.status_code == StatusCode.ERROR
    assert len(span.events) == 1
    assert span.events[0].name == "exception"


def test_start_task_span_attributes(
    bridge: OpenTelemetryBridge,
    memory_exporter: InMemorySpanExporter,
) -> None:
    with bridge.start_task_span("transform_orders", "tkr-456", "wfr-123"):
        pass

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert span.name == "task: transform_orders"
    assert span.status.status_code == StatusCode.OK
    assert span.attributes["task.key"] == "transform_orders"
    assert span.attributes["task.id"] == "transform_orders"
    assert span.attributes["task.run_id"] == "tkr-456"
    assert span.attributes["workflow.run_id"] == "wfr-123"


def test_start_attempt_span_attributes(
    bridge: OpenTelemetryBridge,
    memory_exporter: InMemorySpanExporter,
) -> None:
    with bridge.start_attempt_span(2, "att-789", "subprocess"):
        pass

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert span.name == "attempt: 2"
    assert span.status.status_code == StatusCode.OK
    assert span.attributes["task.attempt_id"] == "att-789"
    assert span.attributes["attempt.number"] == 2
    assert span.attributes["executor.type"] == "subprocess"


def test_record_failure_sets_error_status(
    bridge: OpenTelemetryBridge,
    memory_exporter: InMemorySpanExporter,
) -> None:
    with bridge.start_attempt_span(1, "att-1", "inline"):
        bridge.record_failure("TIMEOUT", "Task exceeded deadline", {"timeout.seconds": 30})

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes["error"] is True
    assert span.attributes["error.code"] == "TIMEOUT"
    assert span.attributes["error.message"] == "Task exceeded deadline"
    assert span.attributes["timeout.seconds"] == 30


def test_record_exception_on_active_span(
    bridge: OpenTelemetryBridge,
    memory_exporter: InMemorySpanExporter,
) -> None:
    with bridge.start_attempt_span(1, "att-1", "inline"):
        bridge.record_exception(RuntimeError("something went wrong"))

    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]

    assert span.status.status_code == StatusCode.ERROR
    assert len(span.events) == 1
    assert span.events[0].name == "exception"


def test_w3c_injection_with_active_span(
    bridge: OpenTelemetryBridge,
) -> None:
    carrier: dict[str, str] = {}
    correlation = CorrelationContext()

    with bridge.start_workflow_span("WfSpan", "wfr-1", correlation):
        bridge.inject_w3c_context(carrier, correlation)

    assert "TRACEPARENT" in carrier
    assert carrier["TRACEPARENT"].startswith("00-")
    parts = carrier["TRACEPARENT"].split("-")
    assert len(parts) == 4
    assert len(parts[1]) == 32  # trace_id (16 bytes hex)
    assert len(parts[2]) == 16  # span_id (8 bytes hex)


def test_w3c_injection_fallback_and_tracestate(
    bridge: OpenTelemetryBridge,
) -> None:
    carrier: dict[str, str] = {"tracestate": "vendor=123"}
    correlation = CorrelationContext().with_w3c_trace(
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        tracestate="congo=t61rcWkgMzE",
    )
    # Outside any active span, fallback to correlation
    bridge.inject_w3c_context(carrier, correlation)
    assert "TRACEPARENT" in carrier
    assert carrier["TRACEPARENT"] == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    assert carrier["TRACESTATE"] == "congo=t61rcWkgMzE"


def test_extract_w3c_context_on_opentelemetry_bridge(
    bridge: OpenTelemetryBridge,
) -> None:
    carrier = {
        "TRACEPARENT": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        "TRACESTATE": "state=xyz",
    }
    tp, ts, trace_id, span_id = bridge.extract_w3c_context(carrier)
    assert tp == carrier["TRACEPARENT"]
    assert ts == "state=xyz"
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert span_id == "00f067aa0ba902b7"

    empty_tp, empty_ts, empty_t, empty_s = bridge.extract_w3c_context({})
    assert empty_tp is None
    assert empty_ts is None
    assert empty_t is None
    assert empty_s is None


def test_get_telemetry_bridge_with_explicit_tracer(tracer_provider: TracerProvider) -> None:
    tracer = tracer_provider.get_tracer("explicit")
    bridge = get_telemetry_bridge(tracer=tracer)
    assert isinstance(bridge, OpenTelemetryBridge)


def test_get_telemetry_bridge_auto_discovery() -> None:
    bridge = get_telemetry_bridge()
    assert isinstance(bridge, OpenTelemetryBridge)


def test_runtime_and_executor_telemetry_type_validation() -> None:
    metadata = InMemoryMetadataStore()
    with pytest.raises(TypeError, match="telemetry must satisfy TelemetryBridge protocol"):
        WorkflowRuntime(metadata=metadata, executor=SubprocessExecutor(), telemetry=object())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="telemetry must satisfy TelemetryBridge protocol"):
        SubprocessExecutor(telemetry=123)  # type: ignore[arg-type]
