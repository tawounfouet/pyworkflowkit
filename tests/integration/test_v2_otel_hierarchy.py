"""Integration tests validating 3-level OpenTelemetry span hierarchy and context lineage."""

from __future__ import annotations

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.diagnostics.failure import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.executors.contracts import TaskExecutionContext, TaskExecutionResult
from pyworkflowkit.executors.inline import InlineExecutor
from pyworkflowkit.persistence.memory import InMemoryMetadataStore
from pyworkflowkit.policies.retry import RetryPolicy
from pyworkflowkit.runtime.telemetry import OpenTelemetryBridge, get_telemetry_bridge
from pyworkflowkit.runtime.workflow import WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus


def test_otel_span_hierarchy_with_retry_and_dependencies() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test_hierarchy")
    bridge = OpenTelemetryBridge(tracer)

    call_counts: dict[str, int] = {"task_2": 0}

    def _task_1_handler() -> str:
        return "data_1"

    def _task_2_handler(ctx: TaskExecutionContext) -> str | TaskExecutionResult:
        call_counts["task_2"] += 1
        if call_counts["task_2"] == 1:
            get_telemetry_bridge().record_exception(ValueError("transient failure on attempt 1"))
            return TaskExecutionResult(
                failure=FailureEvidence(
                    error_code="TRANSIENT_ERROR",
                    category=FailureCategory.TRANSIENT,
                    retryability=Retryability.RETRYABLE,
                    uncertainty=OutcomeUncertainty.KNOWN,
                    correlation_id=ctx.correlation.correlation_id,
                    workflow_run_id=str(ctx.workflow_run_id),
                    task_run_id=str(ctx.task_run_id),
                    task_attempt_id=str(ctx.attempt_id),
                    source_component="inline_executor",
                    message_summary="transient failure on attempt 1",
                )
            )
        return "data_2"

    def _task_3_handler(ctx: object) -> str:
        return "data_3"

    task_1 = TaskDefinition(key="task_1", workload=_task_1_handler)
    task_2 = TaskDefinition(
        key="task_2",
        workload=_task_2_handler,
        dependencies=("task_1",),
        retry_policy=RetryPolicy(max_attempts=2, initial_delay_seconds=0.01),
    )
    task_3 = TaskDefinition(key="task_3", workload=_task_3_handler, dependencies=("task_2",))
    workflow = WorkflowDefinition(
        name="hierarchy_pipeline",
        version="1.0.0",
        tasks=(task_1, task_2, task_3),
    )

    metadata = InMemoryMetadataStore()
    executor = InlineExecutor()
    runtime = WorkflowRuntime(
        metadata=metadata,
        executor=executor,
        telemetry=bridge,
    )

    result = runtime.run(workflow)
    assert result.status == WorkflowRunStatus.SUCCEEDED
    assert result.task("task_1").output == "data_1"
    assert result.task("task_2").output == "data_2"
    assert result.task("task_3").output == "data_3"

    spans = exporter.get_finished_spans()
    spans_by_name = {span.name: span for span in spans if not span.name.startswith("attempt")}
    attempt_spans = [span for span in spans if span.name.startswith("attempt")]

    # 1 Root Workflow Span
    root_span = spans_by_name.get("workflow: hierarchy_pipeline")
    assert root_span is not None
    assert root_span.status.status_code == StatusCode.OK
    root_trace_id = root_span.context.trace_id
    root_span_id = root_span.context.span_id

    # 3 Task Spans
    task_1_span = spans_by_name.get("task: task_1")
    task_2_span = spans_by_name.get("task: task_2")
    task_3_span = spans_by_name.get("task: task_3")

    assert task_1_span is not None
    assert task_2_span is not None
    assert task_3_span is not None

    for t_span in (task_1_span, task_2_span, task_3_span):
        assert t_span.context.trace_id == root_trace_id
        assert t_span.parent.span_id == root_span_id
        assert t_span.status.status_code == StatusCode.OK

    # Attempt Spans
    # task_1 had 1 attempt, task_2 had 2 attempts, task_3 had 1 attempt -> total 4 attempt spans
    assert len(attempt_spans) == 4

    # All attempt spans share root_trace_id
    for a_span in attempt_spans:
        assert a_span.context.trace_id == root_trace_id

    task_1_attempts = [s for s in attempt_spans if s.parent.span_id == task_1_span.context.span_id]
    task_2_attempts = [s for s in attempt_spans if s.parent.span_id == task_2_span.context.span_id]
    task_3_attempts = [s for s in attempt_spans if s.parent.span_id == task_3_span.context.span_id]

    assert len(task_1_attempts) == 1
    assert task_1_attempts[0].attributes["attempt.number"] == 1
    assert task_1_attempts[0].status.status_code == StatusCode.OK

    assert len(task_2_attempts) == 2
    # Sort by attempt number
    task_2_attempts.sort(key=lambda s: int(s.attributes["attempt.number"]))
    failed_attempt = task_2_attempts[0]
    success_attempt = task_2_attempts[1]

    assert failed_attempt.attributes["attempt.number"] == 1
    assert failed_attempt.status.status_code == StatusCode.ERROR
    # Exception event recorded on failed attempt
    assert any(event.name == "exception" for event in failed_attempt.events)

    assert success_attempt.attributes["attempt.number"] == 2
    assert success_attempt.status.status_code == StatusCode.OK

    assert len(task_3_attempts) == 1
    assert task_3_attempts[0].attributes["attempt.number"] == 1
    assert task_3_attempts[0].status.status_code == StatusCode.OK


def test_otel_span_error_recorded_on_workflow_terminal_failure() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test_failure_hierarchy")
    bridge = OpenTelemetryBridge(tracer)

    def _broken_handler() -> str:
        raise RuntimeError("fatal unhandled error")

    task = TaskDefinition(key="broken_task", workload=_broken_handler)
    workflow = WorkflowDefinition(name="failing_pipeline", tasks=(task,))

    metadata = InMemoryMetadataStore()
    runtime = WorkflowRuntime(
        metadata=metadata,
        executor=InlineExecutor(),
        telemetry=bridge,
    )

    result = runtime.run(workflow)
    assert result.status == WorkflowRunStatus.FAILED

    spans = exporter.get_finished_spans()
    root_span = next(s for s in spans if s.name == "workflow: failing_pipeline")
    task_span = next(s for s in spans if s.name == "task: broken_task")
    attempt_span = next(s for s in spans if s.name == "attempt: 1")

    assert root_span.status.status_code == StatusCode.ERROR
    assert task_span.status.status_code == StatusCode.ERROR
    assert attempt_span.status.status_code == StatusCode.ERROR
    assert any(event.name == "exception" for event in attempt_span.events)
