"""Distributed tracing and OpenTelemetry bridge for PyWorkflowKit runtime."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, Protocol, runtime_checkable

from pyworkflowkit.runtime.context import CorrelationContext


@runtime_checkable
class TelemetryBridge(Protocol):
    """Abstract interface for execution tracing and distributed context propagation."""

    @contextmanager
    def start_workflow_span(
        self,
        workflow_name: str,
        run_id: str,
        correlation: CorrelationContext,
        workflow_version: str | None = None,
    ) -> Iterator[Any]:
        """Start a root span representing the end-to-end workflow execution."""
        ...

    @contextmanager
    def start_task_span(
        self,
        task_key: str,
        task_run_id: str,
        workflow_run_id: str,
    ) -> Iterator[Any]:
        """Start a child span representing one logical workflow task execution."""
        ...

    @contextmanager
    def start_attempt_span(
        self,
        attempt_number: int,
        attempt_id: str,
        executor_type: str,
    ) -> Iterator[Any]:
        """Start a leaf span representing one concrete execution attempt."""
        ...

    def inject_w3c_context(
        self,
        carrier: dict[str, str],
        correlation: CorrelationContext | None = None,
    ) -> None:
        """Inject active trace context as standard W3C TRACEPARENT / TRACESTATE headers."""
        ...

    def extract_w3c_context(
        self,
        carrier: Mapping[str, str],
    ) -> tuple[str | None, str | None, str | None, str | None]:
        """Extract (traceparent, tracestate, trace_id, span_id) from carrier."""
        ...

    def record_exception(
        self,
        exc: BaseException,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        """Record an exception on the current active span if supported."""
        ...

    def record_failure(
        self,
        error_code: str,
        message: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        """Record a failure / error status on the active span."""
        ...


class NoOpTelemetryBridge:
    """Default no-op telemetry bridge ensuring zero runtime overhead and no external deps."""

    @contextmanager
    def start_workflow_span(
        self,
        workflow_name: str,
        run_id: str,
        correlation: CorrelationContext,
        workflow_version: str | None = None,
    ) -> Iterator[None]:
        del workflow_name, run_id, correlation, workflow_version
        yield None

    @contextmanager
    def start_task_span(
        self,
        task_key: str,
        task_run_id: str,
        workflow_run_id: str,
    ) -> Iterator[None]:
        del task_key, task_run_id, workflow_run_id
        yield None

    @contextmanager
    def start_attempt_span(
        self,
        attempt_number: int,
        attempt_id: str,
        executor_type: str,
    ) -> Iterator[None]:
        del attempt_number, attempt_id, executor_type
        yield None

    def inject_w3c_context(
        self,
        carrier: dict[str, str],
        correlation: CorrelationContext | None = None,
    ) -> None:
        if correlation is not None and correlation.traceparent:
            carrier["TRACEPARENT"] = correlation.traceparent
            if correlation.tracestate:
                carrier["TRACESTATE"] = correlation.tracestate

    def extract_w3c_context(
        self,
        carrier: Mapping[str, str],
    ) -> tuple[str | None, str | None, str | None, str | None]:
        tp = carrier.get("TRACEPARENT") or carrier.get("traceparent")
        ts = carrier.get("TRACESTATE") or carrier.get("tracestate")
        trace_id = None
        span_id = None
        if tp:
            parts = tp.strip().split("-")
            if len(parts) >= 4:
                trace_id = parts[1]
                span_id = parts[2]
        return tp, ts, trace_id, span_id

    def record_exception(
        self,
        exc: BaseException,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        del exc, attributes

    def record_failure(
        self,
        error_code: str,
        message: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        del error_code, message, attributes


class OpenTelemetryBridge:
    """Production telemetry bridge emitting hierarchical OpenTelemetry spans."""

    def __init__(self, tracer: Any) -> None:
        self._tracer = tracer

    @contextmanager
    def start_workflow_span(
        self,
        workflow_name: str,
        run_id: str,
        correlation: CorrelationContext,
        workflow_version: str | None = None,
    ) -> Iterator[Any]:
        span_name = f"workflow: {workflow_name}"
        attributes: dict[str, Any] = {
            "workflow.name": workflow_name,
            "workflow.run_id": run_id,
            "correlation.id": str(correlation.correlation_id),
        }
        if workflow_version is not None:
            attributes["workflow.version"] = workflow_version
        if correlation.causation_id:
            attributes["correlation.causation_id"] = correlation.causation_id

        with self._tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                yield span
            except BaseException:
                raise
            else:
                self._set_span_ok(span)

    @contextmanager
    def start_task_span(
        self,
        task_key: str,
        task_run_id: str,
        workflow_run_id: str,
    ) -> Iterator[Any]:
        span_name = f"task: {task_key}"
        attributes: dict[str, Any] = {
            "task.key": task_key,
            "task.id": task_key,
            "task.run_id": task_run_id,
            "workflow.run_id": workflow_run_id,
        }
        with self._tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                yield span
            except BaseException:
                raise
            else:
                self._set_span_ok(span)

    @contextmanager
    def start_attempt_span(
        self,
        attempt_number: int,
        attempt_id: str,
        executor_type: str,
    ) -> Iterator[Any]:
        span_name = f"attempt: {attempt_number}"
        attributes: dict[str, Any] = {
            "task.attempt_id": attempt_id,
            "attempt.number": attempt_number,
            "executor.type": executor_type,
        }
        with self._tracer.start_as_current_span(span_name, attributes=attributes) as span:
            try:
                yield span
            except BaseException:
                raise
            else:
                self._set_span_ok(span)

    def inject_w3c_context(
        self,
        carrier: dict[str, str],
        correlation: CorrelationContext | None = None,
    ) -> None:
        try:
            from opentelemetry.trace.propagation.tracecontext import (
                TraceContextTextMapPropagator,
            )

            TraceContextTextMapPropagator().inject(carrier)
        except Exception:  # nosec B110 - fallback if propagator fails
            pass

        if "traceparent" in carrier and "TRACEPARENT" not in carrier:
            carrier["TRACEPARENT"] = carrier["traceparent"]
        if "tracestate" in carrier and "TRACESTATE" not in carrier:
            carrier["TRACESTATE"] = carrier["tracestate"]

        if "TRACEPARENT" not in carrier and correlation is not None and correlation.traceparent:
            carrier["TRACEPARENT"] = correlation.traceparent
            if correlation.tracestate:
                carrier["TRACESTATE"] = correlation.tracestate

    def extract_w3c_context(
        self,
        carrier: Mapping[str, str],
    ) -> tuple[str | None, str | None, str | None, str | None]:
        tp = carrier.get("TRACEPARENT") or carrier.get("traceparent")
        ts = carrier.get("TRACESTATE") or carrier.get("tracestate")
        trace_id = None
        span_id = None
        if tp:
            parts = tp.strip().split("-")
            if len(parts) >= 4:
                trace_id = parts[1]
                span_id = parts[2]
        return tp, ts, trace_id, span_id

    def record_exception(
        self,
        exc: BaseException,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        try:
            import opentelemetry.trace as trace

            span = trace.get_current_span()
            if span and span.is_recording():
                self._record_span_error(span, exc, attributes=attributes)
        except Exception:  # nosec B110 - telemetry must never disrupt execution
            pass

    def record_failure(
        self,
        error_code: str,
        message: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        try:
            import opentelemetry.trace as trace
            from opentelemetry.trace import Status, StatusCode

            span = trace.get_current_span()
            if span and span.is_recording():
                resolved_msg = message or error_code
                attrs: dict[str, Any] = {
                    "error": True,
                    "error.code": error_code,
                    "error.message": resolved_msg,
                }
                if attributes:
                    attrs.update(attributes)
                span.set_attributes(attrs)
                span.set_status(Status(StatusCode.ERROR, resolved_msg))
        except Exception:  # nosec B110 - telemetry must never disrupt execution
            pass

    @staticmethod
    def _record_span_error(
        span: Any,
        exc: BaseException,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        try:
            from opentelemetry.trace import Status, StatusCode

            span.record_exception(exc, attributes=dict(attributes) if attributes else None)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
        except Exception:  # nosec B110 - telemetry must never disrupt execution
            pass

    @staticmethod
    def _set_span_ok(span: Any) -> None:
        try:
            from opentelemetry.trace import Status, StatusCode

            if hasattr(span, "status") and span.status.status_code == StatusCode.ERROR:
                return
            span.set_status(Status(StatusCode.OK))
        except Exception:  # nosec B110 - telemetry must never disrupt execution
            pass


def get_telemetry_bridge(tracer: Any | None = None) -> TelemetryBridge:
    """Discover or build the active TelemetryBridge instance.

    If an explicit tracer is supplied, returns OpenTelemetryBridge with it.
    Otherwise, inspects whether opentelemetry is installed and configured.
    Falls back gracefully to NoOpTelemetryBridge.
    """
    if tracer is not None:
        return OpenTelemetryBridge(tracer)

    try:
        import opentelemetry.trace as trace

        tracer_instance = trace.get_tracer("pyworkflowkit")
        if tracer_instance is not None:
            return OpenTelemetryBridge(tracer_instance)
    except (ImportError, AttributeError, Exception):
        pass

    return NoOpTelemetryBridge()


__all__ = [
    "NoOpTelemetryBridge",
    "OpenTelemetryBridge",
    "TelemetryBridge",
    "get_telemetry_bridge",
]
