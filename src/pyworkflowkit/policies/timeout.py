"""V2 immutable timeout declaration."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

V2_TIMEOUT_CONTRACT_VERSION = "1"


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


def v2_timeout_contract_snapshot() -> dict[str, object]:
    return {
        "contract_version": V2_TIMEOUT_CONTRACT_VERSION,
        "policy_fields": ["execution_timeout"],
        "timeout_means": "local_deadline_exceeded",
        "confirmed_external_stop_required_for_terminal_timeout": True,
    }


__all__ = [
    "TimeoutPolicy",
    "V2_TIMEOUT_CONTRACT_VERSION",
    "v2_timeout_contract_snapshot",
]
