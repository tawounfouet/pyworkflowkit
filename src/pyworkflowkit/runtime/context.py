"""Portable cross-framework execution correlation context."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyworkflowkit.runtime.identity import CorrelationId


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    """Portable correlation metadata for composed executions.

    Correlation connects related work while each framework keeps ownership of
    its own native execution identity.
    """

    correlation_id: CorrelationId = field(default_factory=CorrelationId.new)
    causation_id: str | None = None
    parent_execution_id: str | None = None
    workflow_run_id: str | None = None
    task_run_id: str | None = None
    task_attempt_id: str | None = None
    ingestion_run_id: str | None = None
    transformation_execution_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    traceparent: str | None = None
    tracestate: str | None = None
    baggage: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.correlation_id, CorrelationId):
            raise TypeError("correlation_id must be a CorrelationId")

        for name, value in (
            ("causation_id", self.causation_id),
            ("parent_execution_id", self.parent_execution_id),
            ("workflow_run_id", self.workflow_run_id),
            ("task_run_id", self.task_run_id),
            ("task_attempt_id", self.task_attempt_id),
            ("ingestion_run_id", self.ingestion_run_id),
            ("transformation_execution_id", self.transformation_execution_id),
            ("trace_id", self.trace_id),
            ("span_id", self.span_id),
            ("traceparent", self.traceparent),
            ("tracestate", self.tracestate),
        ):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string when provided")

        if not isinstance(self.baggage, dict):
            raise TypeError("baggage must be a dict")
        for k, v in self.baggage.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise TypeError("baggage keys and values must be strings")

    def with_trace(
        self,
        *,
        trace_id: str,
        span_id: str | None = None,
        traceparent: str | None = None,
        tracestate: str | None = None,
        baggage: dict[str, str] | None = None,
    ) -> CorrelationContext:
        """Return a copy carrying explicit distributed-tracing identifiers."""
        resolved_traceparent = traceparent
        if resolved_traceparent is None and trace_id and span_id:
            resolved_traceparent = f"00-{trace_id.lower()}-{span_id.lower()}-01"

        return CorrelationContext(
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            parent_execution_id=self.parent_execution_id,
            workflow_run_id=self.workflow_run_id,
            task_run_id=self.task_run_id,
            task_attempt_id=self.task_attempt_id,
            ingestion_run_id=self.ingestion_run_id,
            transformation_execution_id=self.transformation_execution_id,
            trace_id=trace_id,
            span_id=span_id,
            traceparent=resolved_traceparent,
            tracestate=tracestate if tracestate is not None else self.tracestate,
            baggage=dict(baggage) if baggage is not None else dict(self.baggage),
        )

    def with_w3c_trace(
        self,
        *,
        traceparent: str,
        tracestate: str | None = None,
        baggage: dict[str, str] | None = None,
    ) -> CorrelationContext:
        """Return a copy parsed from or populated with a standard W3C traceparent header."""
        parts = traceparent.strip().split("-")
        derived_trace_id = parts[1] if len(parts) >= 4 else self.trace_id
        derived_span_id = parts[2] if len(parts) >= 4 else self.span_id

        return CorrelationContext(
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            parent_execution_id=self.parent_execution_id,
            workflow_run_id=self.workflow_run_id,
            task_run_id=self.task_run_id,
            task_attempt_id=self.task_attempt_id,
            ingestion_run_id=self.ingestion_run_id,
            transformation_execution_id=self.transformation_execution_id,
            trace_id=derived_trace_id,
            span_id=derived_span_id,
            traceparent=traceparent.strip(),
            tracestate=tracestate if tracestate is not None else self.tracestate,
            baggage=dict(baggage) if baggage is not None else dict(self.baggage),
        )


__all__ = ["CorrelationContext"]
