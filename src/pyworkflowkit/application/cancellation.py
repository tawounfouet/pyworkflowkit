"""Thread-safe workflow cancellation request primitives."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event, Lock


@dataclass(frozen=True, slots=True)
class CancellationRequest:
    """Immutable first-writer-wins cancellation request."""

    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("cancellation reason must not be blank")


class CancellationController:
    """Thread-safe cancellation signal shared with a running coordinator."""

    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self._request: CancellationRequest | None = None

    @property
    def is_requested(self) -> bool:
        return self._event.is_set()

    @property
    def request_details(self) -> CancellationRequest | None:
        with self._lock:
            return self._request

    def request(self, *, reason: str = "requested") -> bool:
        """Request cancellation once.

        Returns True for the first accepted request and False for later requests.
        The first reason is preserved deterministically.
        """

        request = CancellationRequest(reason=reason)
        with self._lock:
            if self._request is not None:
                return False
            self._request = request
            self._event.set()
            return True


__all__ = ["CancellationController", "CancellationRequest"]
