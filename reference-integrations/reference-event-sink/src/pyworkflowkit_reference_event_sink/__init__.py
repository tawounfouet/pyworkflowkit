"""Independently packaged reference RuntimeEventSink integration."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyworkflowkit.domain.runtime import RuntimeEvent
from pyworkflowkit.plugins import (
    PLUGIN_API_VERSION,
    PluginDescriptor,
    PluginType,
    RegisteredPlugin,
)


@dataclass
class ReferenceEventSink:
    """Record committed RuntimeEvents for conformance assertions."""

    events: list[RuntimeEvent] = field(default_factory=list)

    @property
    def name(self) -> str:
        return "reference-event-sink"

    def emit(self, event: RuntimeEvent) -> None:
        self.events.append(event)


def plugin() -> RegisteredPlugin[ReferenceEventSink]:
    """Return the event-sink plugin registration exposed through entry points."""

    return RegisteredPlugin(
        descriptor=PluginDescriptor(
            name="reference-event-sink",
            plugin_type=PluginType.EVENT,
            api_version=PLUGIN_API_VERSION,
            plugin_version="0.1.0",
            description="Reference independently packaged RuntimeEventSink.",
        ),
        factory=ReferenceEventSink,
    )


__all__ = ["ReferenceEventSink", "plugin"]
