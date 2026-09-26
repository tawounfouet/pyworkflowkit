"""Security boundaries for observability projections."""

from __future__ import annotations

from dataclasses import dataclass, replace

from pyworkflowkit.application.observability import redact_mapping
from pyworkflowkit.domain.runtime import RuntimeEvent

_REDACTED_MESSAGE = "<redacted>"


@dataclass(frozen=True, slots=True)
class ObservabilitySecurityPolicy:
    """Controls what committed runtime evidence may cross into external sinks."""

    redact_event_payloads: bool = True
    expose_sink_error_messages: bool = False
    max_sink_error_message_chars: int = 256

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_sink_error_message_chars, bool)
            or not isinstance(self.max_sink_error_message_chars, int)
        ):
            raise TypeError("max_sink_error_message_chars must be an integer")
        if self.max_sink_error_message_chars < 1:
            raise ValueError("max_sink_error_message_chars must be greater than or equal to 1")

    def event_for_sink(self, event: RuntimeEvent) -> RuntimeEvent:
        """Return the external-observability projection of one durable event."""

        if not self.redact_event_payloads:
            return event
        redacted = redact_mapping(event.payload)
        if redacted == dict(event.payload):
            return event
        return replace(event, payload=redacted)

    def sink_error_message(self, exc: Exception) -> str:
        """Return a bounded, policy-controlled diagnostic message."""

        if not self.expose_sink_error_messages:
            return _REDACTED_MESSAGE
        message = str(exc) or type(exc).__name__
        return message[: self.max_sink_error_message_chars]


__all__ = ["ObservabilitySecurityPolicy"]
