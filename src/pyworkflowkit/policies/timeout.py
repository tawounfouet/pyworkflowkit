"""V2 immutable timeout declaration."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class TimeoutPolicy:
    """Local workload execution deadline declaration.

    A local timeout never implies that external work has been confirmed stopped.
    LOT-08 expands cancellation and reconciliation semantics.
    """

    execution_timeout: float | None = None

    def __post_init__(self) -> None:
        value = self.execution_timeout
        if value is None:
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("execution_timeout must be a finite number or None")
        if not isfinite(value):
            raise ValueError("execution_timeout must be finite")
        if value <= 0:
            raise ValueError("execution_timeout must be greater than 0")


__all__ = ["TimeoutPolicy"]
