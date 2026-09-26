"""Runtime-event observability dispatch.

RuntimeEvents remain the durable source of execution history. Observability sinks receive
only events whose UnitOfWork commit has already succeeded.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pyworkflowkit.application.observability import LogContext, log_runtime
from pyworkflowkit.domain.runtime import RuntimeEvent
from pyworkflowkit.ports.observability import RuntimeEventSink

logger = logging.getLogger("pyworkflowkit.observability.dispatcher")


@dataclass(frozen=True, slots=True)
class ObservabilityDispatchFailure:
    """One isolated sink failure recorded for runtime diagnostics."""

    sink_name: str
    event_id: str
    event_type: str
    error_type: str
    error_message: str


class ObservabilityDispatcher:
    """Best-effort fan-out of committed RuntimeEvents to external sinks."""

    def __init__(self, sinks: tuple[RuntimeEventSink, ...] = ()) -> None:
        self._sinks: dict[str, RuntimeEventSink] = {}
        self._failures: list[ObservabilityDispatchFailure] = []
        for sink in sinks:
            self.register(sink)

    def register(self, sink: RuntimeEventSink) -> None:
        """Register one sink by stable name."""

        name = sink.name.strip()
        if not name:
            raise ValueError("observability sink name must not be blank")
        if name in self._sinks:
            raise ValueError(f"observability sink '{name}' is already registered")
        self._sinks[name] = sink

    @property
    def sink_names(self) -> tuple[str, ...]:
        """Return registered sink names in deterministic order."""

        return tuple(sorted(self._sinks))

    @property
    def failures(self) -> tuple[ObservabilityDispatchFailure, ...]:
        """Return isolated sink failures in observation order."""

        return tuple(self._failures)

    def publish(self, event: RuntimeEvent) -> None:
        """Fan out one committed RuntimeEvent without affecting runtime correctness."""

        for name in self.sink_names:
            sink = self._sinks[name]
            try:
                sink.emit(event)
            except Exception as exc:
                failure = ObservabilityDispatchFailure(
                    sink_name=name,
                    event_id=str(event.event_id),
                    event_type=event.event_type.value,
                    error_type=type(exc).__name__,
                    error_message=str(exc) or type(exc).__name__,
                )
                self._failures.append(failure)
                log_runtime(
                    logger,
                    logging.WARNING,
                    "Observability sink failed",
                    context=LogContext(
                        run_id=str(event.run_id),
                        task_run_id=(
                            str(event.task_run_id) if event.task_run_id is not None else None
                        ),
                        task_id=str(event.task_id) if event.task_id is not None else None,
                        attempt_number=event.attempt_number,
                    ),
                    fields={
                        "sink_name": name,
                        "event_id": str(event.event_id),
                        "event_type": event.event_type.value,
                        "error_type": failure.error_type,
                    },
                )


__all__ = ["ObservabilityDispatchFailure", "ObservabilityDispatcher"]
