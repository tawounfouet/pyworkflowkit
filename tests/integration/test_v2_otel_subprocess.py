"""Integration tests validating W3C TRACEPARENT propagation to external subprocesses."""

from __future__ import annotations

import json
import sys

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.executors import ExecutorRegistry
from pyworkflowkit.executors.subprocess import (
    SubprocessCommand,
    SubprocessExecutor,
    SubprocessResult,
)
from pyworkflowkit.persistence.memory import InMemoryMetadataStore
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.identity import CorrelationId
from pyworkflowkit.runtime.telemetry import OpenTelemetryBridge
from pyworkflowkit.runtime.workflow import WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus


def test_subprocess_inherits_w3c_traceparent_from_parent_workflow() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test_subprocess_w3c")
    bridge = OpenTelemetryBridge(tracer)

    python_snippet = (
        "import json, os; "
        "print(json.dumps({"
        "'traceparent': os.environ.get('TRACEPARENT', ''), "
        "'tracestate': os.environ.get('TRACESTATE', '')"
        "}))"
    )
    cmd = SubprocessCommand(argv=(sys.executable, "-c", python_snippet))

    task = TaskDefinition(key="run_script", workload=cmd)
    workflow = WorkflowDefinition(name="subprocess_tracing_workflow", tasks=(task,))

    metadata = InMemoryMetadataStore()
    subprocess_executor = SubprocessExecutor(max_workers=1, telemetry=bridge)
    registry = ExecutorRegistry((subprocess_executor,))

    runtime = WorkflowRuntime(
        executor_registry=registry,
        metadata=metadata,
        telemetry=bridge,
    )

    result = runtime.run(workflow)
    assert result.status == WorkflowRunStatus.SUCCEEDED

    task_outcome = result.task("run_script")
    sub_res = task_outcome.output
    assert isinstance(sub_res, SubprocessResult)
    assert sub_res.returncode == 0

    captured = json.loads(sub_res.stdout.strip())
    child_traceparent = captured["traceparent"]
    assert child_traceparent != ""
    assert child_traceparent.startswith("00-")

    parts = child_traceparent.split("-")
    assert len(parts) == 4
    child_trace_id = parts[1]
    child_parent_span_id = parts[2]

    # Verify against finished spans in exporter
    spans = exporter.get_finished_spans()
    root_span = next(s for s in spans if s.name == "workflow: subprocess_tracing_workflow")
    attempt_span = next(s for s in spans if s.name == "attempt: 1")

    expected_trace_id = format(root_span.context.trace_id, "032x")
    expected_attempt_span_id = format(attempt_span.context.span_id, "016x")

    assert child_trace_id == expected_trace_id
    assert child_parent_span_id == expected_attempt_span_id


def test_subprocess_inherits_explicit_incoming_w3c_traceparent() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test_incoming_w3c")
    bridge = OpenTelemetryBridge(tracer)

    python_snippet = (
        "import json, os; print(json.dumps({'traceparent': os.environ.get('TRACEPARENT', '')}))"
    )
    cmd = SubprocessCommand(argv=(sys.executable, "-c", python_snippet))

    task = TaskDefinition(key="external_call", workload=cmd)
    workflow = WorkflowDefinition(name="incoming_w3c_flow", tasks=(task,))

    metadata = InMemoryMetadataStore()
    subprocess_executor = SubprocessExecutor(max_workers=1, telemetry=bridge)
    registry = ExecutorRegistry((subprocess_executor,))

    runtime = WorkflowRuntime(
        executor_registry=registry,
        metadata=metadata,
        telemetry=bridge,
    )

    # Simulate an incoming request carrying an external W3C traceparent
    incoming_tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    incoming_correlation = CorrelationContext(
        correlation_id=CorrelationId.parse("C-ext"),
    ).with_w3c_trace(traceparent=incoming_tp)

    result = runtime.run(workflow, correlation=incoming_correlation)
    assert result.status == WorkflowRunStatus.SUCCEEDED

    task_outcome = result.task("external_call")
    sub_res = task_outcome.output
    assert isinstance(sub_res, SubprocessResult)

    captured = json.loads(sub_res.stdout.strip())
    child_traceparent = captured["traceparent"]
    assert child_traceparent != ""

    parts = child_traceparent.split("-")
    assert len(parts) == 4
    # The child inherits a valid W3C header
    assert len(parts[1]) == 32
    assert len(parts[2]) == 16
