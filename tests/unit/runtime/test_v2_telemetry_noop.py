"""Unit tests verifying NoOpTelemetryBridge transparent zero-overhead behavior."""

from __future__ import annotations

import sys
from unittest.mock import patch

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.executors.inline import InlineExecutor
from pyworkflowkit.persistence.memory import InMemoryMetadataStore
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.telemetry import (
    NoOpTelemetryBridge,
    TelemetryBridge,
    get_telemetry_bridge,
)
from pyworkflowkit.runtime.workflow import WorkflowRuntime


def test_noop_telemetry_bridge_satisfies_protocol() -> None:
    bridge = NoOpTelemetryBridge()
    assert isinstance(bridge, TelemetryBridge)


def test_noop_telemetry_bridge_context_managers() -> None:
    bridge = NoOpTelemetryBridge()
    correlation = CorrelationContext()

    with bridge.start_workflow_span(
        "test_wf", "run-1", correlation, workflow_version="1.0"
    ) as span:
        assert span is None

    with bridge.start_task_span("task_a", "tr-1", "run-1") as span:
        assert span is None

    with bridge.start_attempt_span(1, "att-1", "inline") as span:
        assert span is None


def test_noop_telemetry_bridge_w3c_injection_and_extraction() -> None:
    bridge = NoOpTelemetryBridge()

    # Empty carrier / None correlation
    carrier: dict[str, str] = {}
    bridge.inject_w3c_context(carrier, None)
    assert carrier == {}

    # Correlation without traceparent
    correlation_no_trace = CorrelationContext()
    bridge.inject_w3c_context(carrier, correlation_no_trace)
    assert carrier == {}

    # Correlation with traceparent and tracestate
    tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    ts = "congo=t61rcWkgMzE"
    correlation_with_trace = correlation_no_trace.with_w3c_trace(traceparent=tp, tracestate=ts)
    bridge.inject_w3c_context(carrier, correlation_with_trace)
    assert carrier["TRACEPARENT"] == tp
    assert carrier["TRACESTATE"] == ts

    # Extraction
    extracted_tp, extracted_ts, trace_id, span_id = bridge.extract_w3c_context(carrier)
    assert extracted_tp == tp
    assert extracted_ts == ts
    assert trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert span_id == "00f067aa0ba902b7"

    # Empty extraction
    empty_tp, empty_ts, empty_trace, empty_span = bridge.extract_w3c_context({})
    assert empty_tp is None
    assert empty_ts is None
    assert empty_trace is None
    assert empty_span is None


def test_noop_telemetry_bridge_record_methods_safe() -> None:
    bridge = NoOpTelemetryBridge()
    bridge.record_exception(RuntimeError("test error"))
    bridge.record_failure("ERR_CODE", "Something broke")


def test_get_telemetry_bridge_fallback_when_opentelemetry_absent() -> None:
    with patch.dict(sys.modules, {"opentelemetry": None, "opentelemetry.trace": None}):
        bridge = get_telemetry_bridge()
        assert isinstance(bridge, NoOpTelemetryBridge)


def test_workflow_runtime_nominal_with_noop_telemetry() -> None:
    task_1 = TaskDefinition(key="task_1", workload=lambda: "val_1")
    task_2 = TaskDefinition(
        key="task_2",
        workload=lambda ctx: f"val_2_{ctx.dependency_outputs['task_1']}",
        dependencies=("task_1",),
    )
    wf = WorkflowDefinition(name="test_workflow", tasks=(task_1, task_2))

    metadata = InMemoryMetadataStore()
    executor = InlineExecutor()
    runtime = WorkflowRuntime(
        metadata=metadata,
        executor=executor,
        telemetry=NoOpTelemetryBridge(),
    )

    result = runtime.run(wf)
    from pyworkflowkit.states import WorkflowRunStatus

    assert result.status == WorkflowRunStatus.SUCCEEDED
    assert result.task("task_1").output == "val_1"
    assert result.task("task_2").output == "val_2_val_1"
