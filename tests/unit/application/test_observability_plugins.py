"""Tests for M35 observability plugin dispatch."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from pyworkflowkit.application.observability_plugins import ObservabilityDispatcher
from pyworkflowkit.domain.enums import RuntimeEventType
from pyworkflowkit.domain.ids import RuntimeEventId, WorkflowRunId
from pyworkflowkit.domain.runtime import RuntimeEvent
from pyworkflowkit.plugins import PluginCatalog, PluginDescriptor, PluginType
from pyworkflowkit.ports.observability import RuntimeEventSink

NOW = datetime(2026, 9, 26, 20, 0, tzinfo=UTC)


def _event(sequence: int = 1) -> RuntimeEvent:
    return RuntimeEvent(
        event_id=RuntimeEventId(f"event-{sequence}"),
        event_type=RuntimeEventType.WORKFLOW_STARTED,
        run_id=WorkflowRunId("run-1"),
        occurred_at=NOW,
        event_sequence=sequence,
    )


@dataclass
class RecordingSink:
    name: str
    events: list[RuntimeEvent] = field(default_factory=list)

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)


@dataclass
class BrokenSink:
    name: str = "broken"

    def emit(self, event: RuntimeEvent) -> None:
        del event
        raise RuntimeError("export unavailable")


def test_dispatcher_publishes_to_sinks_in_deterministic_name_order() -> None:
    observed: list[str] = []

    @dataclass
    class OrderedSink:
        name: str

        def emit(self, event: RuntimeEvent) -> None:
            del event
            observed.append(self.name)

    dispatcher = ObservabilityDispatcher(
        sinks=(OrderedSink("zeta"), OrderedSink("alpha")),
    )

    dispatcher.publish(_event())

    assert observed == ["alpha", "zeta"]
    assert dispatcher.sink_names == ("alpha", "zeta")


def test_dispatcher_isolates_sink_failure_and_continues_fanout() -> None:
    recording = RecordingSink("recording")
    dispatcher = ObservabilityDispatcher(
        sinks=(BrokenSink(), recording),
    )
    event = _event()

    dispatcher.publish(event)

    assert recording.events == [event]
    assert len(dispatcher.failures) == 1
    failure = dispatcher.failures[0]
    assert failure.sink_name == "broken"
    assert failure.event_id == "event-1"
    assert failure.event_type == RuntimeEventType.WORKFLOW_STARTED.value
    assert failure.error_type == "RuntimeError"
    assert failure.error_message == "export unavailable"


def test_dispatcher_rejects_blank_and_duplicate_sink_names() -> None:
    dispatcher = ObservabilityDispatcher()

    with pytest.raises(ValueError, match="must not be blank"):
        dispatcher.register(RecordingSink(" "))

    dispatcher.register(RecordingSink("events"))
    with pytest.raises(ValueError, match="already registered"):
        dispatcher.register(RecordingSink("events"))


def test_runtime_event_sink_is_runtime_checkable() -> None:
    assert isinstance(RecordingSink("events"), RuntimeEventSink)


def test_event_plugin_registry_is_typed_for_runtime_event_sinks() -> None:
    sink = RecordingSink("plugin-events")
    catalog = PluginCatalog()
    descriptor = PluginDescriptor(
        name="plugin-events",
        plugin_type=PluginType.EVENT,
        plugin_version="1.0.0",
    )

    catalog.events.register(descriptor, lambda: sink)

    created = catalog.events.create("plugin-events")
    assert isinstance(created, RuntimeEventSink)
    assert created is sink
    assert catalog.registry_for(PluginType.EVENT).descriptors() == (descriptor,)
