"""Bounded execution-capacity accounting for future concurrent dispatch."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType

from pyworkflowkit.domain.ids import TaskAttemptId, validate_non_empty_identifier
from pyworkflowkit.errors import (
    CapacityConfigurationError,
    CapacityInvariantError,
    CapacityReleaseError,
)
from pyworkflowkit.ports.executor import ExecutorCapabilities


@dataclass(frozen=True, slots=True)
class CapacityLease:
    """One active execution reservation."""

    attempt_id: TaskAttemptId
    executor_key: str


@dataclass(frozen=True, slots=True)
class ExecutorCapacitySnapshot:
    """Current slot usage for one executor."""

    executor_key: str
    limit: int
    active: int

    @property
    def available(self) -> int:
        return self.limit - self.active


@dataclass(frozen=True, slots=True)
class CapacitySnapshot:
    """Immutable global capacity view."""

    global_limit: int
    active_attempts: int
    executors: Mapping[str, ExecutorCapacitySnapshot]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "executors",
            MappingProxyType(dict(self.executors)),
        )

    @property
    def available_global_slots(self) -> int:
        return self.global_limit - self.active_attempts


class CapacityManager:
    """Thread-safe slot accounting without dispatching work itself."""

    def __init__(
        self,
        *,
        global_limit: int,
        executor_capabilities: Mapping[str, ExecutorCapabilities],
        per_executor_limits: Mapping[str, int] | None = None,
    ) -> None:
        self._global_limit = _validate_positive_limit(global_limit, field_name="global_limit")
        if not executor_capabilities:
            raise CapacityConfigurationError("executor_capabilities must not be empty")

        normalized_capabilities: dict[str, ExecutorCapabilities] = {}
        for executor_key, capabilities in executor_capabilities.items():
            validate_non_empty_identifier(executor_key, field_name="executor_key")
            if not isinstance(capabilities, ExecutorCapabilities):
                raise TypeError("executor_capabilities values must be ExecutorCapabilities")
            normalized_capabilities[executor_key] = capabilities

        configured_limits = dict(per_executor_limits or {})
        unknown_limits = sorted(set(configured_limits) - set(normalized_capabilities))
        if unknown_limits:
            raise CapacityConfigurationError(
                "per_executor_limits contains unknown executors: " + ", ".join(unknown_limits)
            )

        effective_limits: dict[str, int] = {}
        for executor_key, capabilities in normalized_capabilities.items():
            configured = configured_limits.get(executor_key, capabilities.max_concurrency)
            configured = _validate_positive_limit(
                configured,
                field_name=f"per_executor_limits[{executor_key!r}]",
            )
            effective_limits[executor_key] = min(
                configured,
                capabilities.max_concurrency,
            )

        self._executor_limits = effective_limits
        self._active_by_attempt: dict[TaskAttemptId, str] = {}
        self._active_by_executor: dict[str, int] = {
            executor_key: 0 for executor_key in effective_limits
        }
        self._lock = RLock()

    @property
    def global_limit(self) -> int:
        return self._global_limit

    def try_acquire(
        self,
        *,
        executor_key: str,
        attempt_id: TaskAttemptId,
    ) -> CapacityLease | None:
        """Reserve a slot if both global and executor capacity are available."""

        validate_non_empty_identifier(executor_key, field_name="executor_key")
        validate_non_empty_identifier(str(attempt_id), field_name="attempt_id")

        with self._lock:
            self._require_known_executor(executor_key)

            if attempt_id in self._active_by_attempt:
                raise CapacityInvariantError(f"attempt '{attempt_id}' already owns a capacity slot")

            if len(self._active_by_attempt) >= self._global_limit:
                return None

            if self._active_by_executor[executor_key] >= self._executor_limits[executor_key]:
                return None

            self._active_by_attempt[attempt_id] = executor_key
            self._active_by_executor[executor_key] += 1
            return CapacityLease(
                attempt_id=attempt_id,
                executor_key=executor_key,
            )

    def release(self, lease: CapacityLease) -> None:
        """Release exactly one previously acquired slot."""

        with self._lock:
            registered_executor = self._active_by_attempt.get(lease.attempt_id)
            if registered_executor is None:
                raise CapacityReleaseError(
                    f"attempt '{lease.attempt_id}' does not own an active capacity slot"
                )
            if registered_executor != lease.executor_key:
                raise CapacityReleaseError(
                    f"attempt '{lease.attempt_id}' owns executor slot "
                    f"'{registered_executor}', not '{lease.executor_key}'"
                )

            del self._active_by_attempt[lease.attempt_id]
            self._active_by_executor[lease.executor_key] -= 1

            if self._active_by_executor[lease.executor_key] < 0:
                raise CapacityInvariantError(
                    f"executor '{lease.executor_key}' active slot count became negative"
                )

    def snapshot(self) -> CapacitySnapshot:
        """Return an immutable point-in-time capacity view."""

        with self._lock:
            executors = {
                executor_key: ExecutorCapacitySnapshot(
                    executor_key=executor_key,
                    limit=self._executor_limits[executor_key],
                    active=self._active_by_executor[executor_key],
                )
                for executor_key in sorted(self._executor_limits)
            }
            return CapacitySnapshot(
                global_limit=self._global_limit,
                active_attempts=len(self._active_by_attempt),
                executors=executors,
            )

    def active_attempts(self) -> tuple[CapacityLease, ...]:
        """Return active reservations deterministically by attempt identifier."""

        with self._lock:
            return tuple(
                CapacityLease(
                    attempt_id=attempt_id,
                    executor_key=self._active_by_attempt[attempt_id],
                )
                for attempt_id in sorted(self._active_by_attempt, key=str)
            )

    def _require_known_executor(self, executor_key: str) -> None:
        if executor_key not in self._executor_limits:
            raise CapacityConfigurationError(
                f"executor '{executor_key}' has no registered capacity contract"
            )


def _validate_positive_limit(value: int, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 1:
        raise CapacityConfigurationError(f"{field_name} must be greater than or equal to 1")
    return value


__all__ = [
    "CapacityLease",
    "CapacityManager",
    "CapacitySnapshot",
    "ExecutorCapacitySnapshot",
]
