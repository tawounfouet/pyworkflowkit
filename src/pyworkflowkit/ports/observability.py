"""Observability extension ports."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pyworkflowkit.domain.runtime import RuntimeEvent


@runtime_checkable
class RuntimeEventSink(Protocol):
    """Receive committed runtime events for external observability projection."""

    @property
    def name(self) -> str:
        """Stable sink name used for diagnostics."""

    def emit(self, event: RuntimeEvent) -> None:
        """Observe one already-persisted RuntimeEvent."""


__all__ = ["RuntimeEventSink"]
