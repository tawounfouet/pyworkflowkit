"""Vendor-neutral observability interoperability projections.

M49 keeps RuntimeEvent as the durable source of truth and projects committed, redacted
events into backend-neutral telemetry records. Telemetry remains secondary evidence:
backend failures never own workflow correctness.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from pyworkflowkit.application.observability import redact_mapping
from pyworkflowkit.domain.enums import RuntimeEventType
from pyworkflowkit.domain.runtime import RuntimeEvent

OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION = "1"

TelemetryAttributeValue = str | bool | int | float


class TelemetryMetricKind(StrEnum):
    """Backend-neutral metric instrument kind."""

    COUNTER = "counter"
    HISTOGRAM = "histogram"


@dataclass(frozen=True, slots=True)
class TelemetryCorrelation:
    """Stable PyWorkflowKit identities used to correlate one telemetry event."""

    event_id: str
    run_id: str
    task_run_id: str | None = None
    task_id: str | None = None
    attempt_number: int | None = None
    event_sequence: int | None = None

    def attributes(self) -> Mapping[str, TelemetryAttributeValue]:
        values: dict[str, TelemetryAttributeValue] = {
            "pyworkflowkit.event_id": self.event_id,
            "pyworkflowkit.run_id": self.run_id,
        }
        if self.task_run_id is not None:
            values["pyworkflowkit.task_run_id"] = self.task_run_id
        if self.task_id is not None:
            values["pyworkflowkit.task_id"] = self.task_id
        if self.attempt_number is not None:
            values["pyworkflowkit.attempt_number"] = self.attempt_number
        if self.event_sequence is not None:
            values["pyworkflowkit.event_sequence"] = self.event_sequence
        return MappingProxyType(values)


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    """Portable event projection suitable for tracing/logging backends."""

    name: str
    occurred_at: datetime
    correlation: TelemetryCorrelation
    attributes: Mapping[str, TelemetryAttributeValue] = field(default_factory=dict)
    payload: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("telemetry event name must not be blank")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True, slots=True)
class TelemetryMetric:
    """One backend-neutral metric observation."""

    name: str
    kind: TelemetryMetricKind
    value: float
    occurred_at: datetime
    unit: str = "1"
    attributes: Mapping[str, TelemetryAttributeValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("telemetry metric name must not be blank")
        if not isinstance(self.kind, TelemetryMetricKind):
            raise TypeError("telemetry metric kind must be a TelemetryMetricKind")
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise TypeError("telemetry metric value must be numeric")
        if not isfinite(float(self.value)):
            raise ValueError("telemetry metric value must be finite")
        if not self.unit.strip():
            raise ValueError("telemetry metric unit must not be blank")
        object.__setattr__(self, "value", float(self.value))
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


@dataclass(frozen=True, slots=True)
class TelemetryProjection:
    """One projected telemetry event and its generic runtime metrics."""

    event: TelemetryEvent
    metrics: tuple[TelemetryMetric, ...] = ()


@runtime_checkable
class TelemetryBackend(Protocol):
    """Consume backend-neutral telemetry records."""

    @property
    def name(self) -> str:
        """Stable backend name used by RuntimeTelemetrySink."""

    def emit_event(self, event: TelemetryEvent) -> None:
        """Emit one telemetry event."""

    def record_metric(self, metric: TelemetryMetric) -> None:
        """Record one metric observation."""


class RuntimeTelemetryProjector:
    """Project committed runtime events into portable telemetry records."""

    _WORKFLOW_TERMINAL = {
        RuntimeEventType.WORKFLOW_SUCCEEDED: "succeeded",
        RuntimeEventType.WORKFLOW_FAILED: "failed",
        RuntimeEventType.WORKFLOW_CANCELLED: "cancelled",
    }
    _TASK_TERMINAL = {
        RuntimeEventType.TASK_SUCCEEDED: "succeeded",
        RuntimeEventType.TASK_FAILED: "failed",
        RuntimeEventType.TASK_SKIPPED: "skipped",
    }

    def __init__(self) -> None:
        self._workflow_started_at: dict[str, datetime] = {}
        self._task_started_at: dict[str, datetime] = {}

    def project(self, event: RuntimeEvent) -> TelemetryProjection:
        """Project one RuntimeEvent without mutating durable runtime state."""

        correlation = TelemetryCorrelation(
            event_id=str(event.event_id),
            run_id=str(event.run_id),
            task_run_id=(str(event.task_run_id) if event.task_run_id is not None else None),
            task_id=(str(event.task_id) if event.task_id is not None else None),
            attempt_number=event.attempt_number,
            event_sequence=event.event_sequence,
        )
        telemetry_event = TelemetryEvent(
            name=f"pyworkflowkit.runtime.{event.event_type.value.lower()}",
            occurred_at=event.occurred_at,
            correlation=correlation,
            attributes={
                "pyworkflowkit.event_type": event.event_type.value,
            },
            payload=redact_mapping(event.payload),
        )

        metrics: list[TelemetryMetric] = [
            _counter(
                "pyworkflowkit.runtime.events",
                event=event,
                attributes={"event_type": event.event_type.value},
            )
        ]

        if event.event_type is RuntimeEventType.WORKFLOW_STARTED:
            self._workflow_started_at.setdefault(str(event.run_id), event.occurred_at)
            metrics.append(_counter("pyworkflowkit.workflow.started", event=event))

        workflow_outcome = self._WORKFLOW_TERMINAL.get(event.event_type)
        if workflow_outcome is not None:
            metrics.append(
                _counter(
                    "pyworkflowkit.workflow.completed",
                    event=event,
                    attributes={"outcome": workflow_outcome},
                )
            )
            started_at = self._workflow_started_at.pop(str(event.run_id), None)
            if started_at is not None:
                metrics.append(
                    _duration(
                        "pyworkflowkit.workflow.duration",
                        started_at=started_at,
                        event=event,
                        attributes={"outcome": workflow_outcome},
                    )
                )

        if event.event_type is RuntimeEventType.TASK_STARTED:
            if event.task_run_id is not None:
                self._task_started_at.setdefault(
                    str(event.task_run_id),
                    event.occurred_at,
                )
            metrics.append(_counter("pyworkflowkit.task.started", event=event))

        if event.event_type is RuntimeEventType.TASK_RETRYING:
            metrics.append(_counter("pyworkflowkit.task.retries", event=event))

        task_outcome = self._TASK_TERMINAL.get(event.event_type)
        if task_outcome is not None:
            metrics.append(
                _counter(
                    "pyworkflowkit.task.completed",
                    event=event,
                    attributes={"outcome": task_outcome},
                )
            )
            if event.task_run_id is not None:
                started_at = self._task_started_at.pop(str(event.task_run_id), None)
                if started_at is not None:
                    metrics.append(
                        _duration(
                            "pyworkflowkit.task.duration",
                            started_at=started_at,
                            event=event,
                            attributes={"outcome": task_outcome},
                        )
                    )

        return TelemetryProjection(event=telemetry_event, metrics=tuple(metrics))


class RuntimeTelemetrySink:
    """Adapt one TelemetryBackend to the existing RuntimeEventSink contract."""

    def __init__(
        self,
        backend: TelemetryBackend,
        *,
        projector: RuntimeTelemetryProjector | None = None,
    ) -> None:
        name = backend.name.strip()
        if not name:
            raise ValueError("telemetry backend name must not be blank")
        self._backend = backend
        self._projector = projector or RuntimeTelemetryProjector()
        self._name = f"telemetry:{name}"

    @property
    def name(self) -> str:
        return self._name

    def emit(self, event: RuntimeEvent) -> None:
        projection = self._projector.project(event)
        self._backend.emit_event(projection.event)
        for metric in projection.metrics:
            self._backend.record_metric(metric)


class _OpenTelemetrySpan(Protocol):
    def set_attribute(self, key: str, value: TelemetryAttributeValue) -> object: ...

    def add_event(
        self,
        name: str,
        attributes: Mapping[str, TelemetryAttributeValue] | None = None,
    ) -> object: ...


class OpenTelemetryTracer(Protocol):
    """Subset of the OpenTelemetry tracer API used by the reference adapter."""

    def start_as_current_span(
        self,
        name: str,
    ) -> AbstractContextManager[_OpenTelemetrySpan]: ...


class _OpenTelemetryCounter(Protocol):
    def add(
        self,
        amount: int | float,
        attributes: Mapping[str, TelemetryAttributeValue] | None = None,
    ) -> object: ...


class _OpenTelemetryHistogram(Protocol):
    def record(
        self,
        amount: int | float,
        attributes: Mapping[str, TelemetryAttributeValue] | None = None,
    ) -> object: ...


class OpenTelemetryMeter(Protocol):
    """Subset of the OpenTelemetry meter API used by the reference adapter."""

    def create_counter(
        self,
        name: str,
        *,
        unit: str = "",
    ) -> _OpenTelemetryCounter: ...

    def create_histogram(
        self,
        name: str,
        *,
        unit: str = "",
    ) -> _OpenTelemetryHistogram: ...


class OpenTelemetryBackend:
    """Dependency-free adapter around injected OpenTelemetry tracer/meter objects.

    PyWorkflowKit does not import OpenTelemetry. Applications that already use the
    OpenTelemetry API may inject their own tracer and meter instances.
    """

    def __init__(
        self,
        *,
        tracer: OpenTelemetryTracer,
        meter: OpenTelemetryMeter,
        name: str = "opentelemetry",
    ) -> None:
        if not name.strip():
            raise ValueError("OpenTelemetry backend name must not be blank")
        self._tracer = tracer
        self._meter = meter
        self._name = name
        self._counters: dict[tuple[str, str], _OpenTelemetryCounter] = {}
        self._histograms: dict[tuple[str, str], _OpenTelemetryHistogram] = {}

    @property
    def name(self) -> str:
        return self._name

    def emit_event(self, event: TelemetryEvent) -> None:
        correlation = event.correlation.attributes()
        with self._tracer.start_as_current_span(event.name) as span:
            for key, value in correlation.items():
                span.set_attribute(key, value)
            for key, value in event.attributes.items():
                span.set_attribute(key, value)
            event_attributes: dict[str, TelemetryAttributeValue] = dict(correlation)
            event_attributes.update(event.attributes)
            if event.payload:
                event_attributes["pyworkflowkit.payload_json"] = json.dumps(
                    event.payload,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            span.add_event(event.name, attributes=event_attributes)

    def record_metric(self, metric: TelemetryMetric) -> None:
        key = (metric.name, metric.unit)
        if metric.kind is TelemetryMetricKind.COUNTER:
            counter = self._counters.get(key)
            if counter is None:
                counter = self._meter.create_counter(metric.name, unit=metric.unit)
                self._counters[key] = counter
            counter.add(metric.value, attributes=metric.attributes)
            return

        histogram = self._histograms.get(key)
        if histogram is None:
            histogram = self._meter.create_histogram(metric.name, unit=metric.unit)
            self._histograms[key] = histogram
        histogram.record(metric.value, attributes=metric.attributes)


def _counter(
    name: str,
    *,
    event: RuntimeEvent,
    attributes: Mapping[str, TelemetryAttributeValue] | None = None,
) -> TelemetryMetric:
    return TelemetryMetric(
        name=name,
        kind=TelemetryMetricKind.COUNTER,
        value=1.0,
        occurred_at=event.occurred_at,
        attributes=attributes or {},
    )


def _duration(
    name: str,
    *,
    started_at: datetime,
    event: RuntimeEvent,
    attributes: Mapping[str, TelemetryAttributeValue],
) -> TelemetryMetric:
    duration = max(0.0, (event.occurred_at - started_at).total_seconds())
    return TelemetryMetric(
        name=name,
        kind=TelemetryMetricKind.HISTOGRAM,
        value=duration,
        occurred_at=event.occurred_at,
        unit="s",
        attributes=attributes,
    )


__all__ = [
    "OBSERVABILITY_INTEROPERABILITY_CONTRACT_VERSION",
    "OpenTelemetryBackend",
    "OpenTelemetryMeter",
    "OpenTelemetryTracer",
    "RuntimeTelemetryProjector",
    "RuntimeTelemetrySink",
    "TelemetryBackend",
    "TelemetryCorrelation",
    "TelemetryEvent",
    "TelemetryMetric",
    "TelemetryMetricKind",
    "TelemetryProjection",
]
