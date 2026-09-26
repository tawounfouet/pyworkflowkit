"""Execution-handle and completion-transfer primitives for concurrent executors."""

from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue

from pyworkflowkit.domain.ids import TaskAttemptId, validate_non_empty_identifier
from pyworkflowkit.domain.values import TaskResult
from pyworkflowkit.errors import ExecutorError


@dataclass(frozen=True, slots=True)
class ExecutionHandle:
    """Opaque identity for one submitted task attempt."""

    handle_id: str
    attempt_id: TaskAttemptId
    executor_key: str

    def __post_init__(self) -> None:
        validate_non_empty_identifier(self.handle_id, field_name="handle_id")
        validate_non_empty_identifier(str(self.attempt_id), field_name="attempt_id")
        validate_non_empty_identifier(self.executor_key, field_name="executor_key")


@dataclass(frozen=True, slots=True)
class AttemptCompletion:
    """Terminal worker outcome transferred back to the coordinator."""

    handle: ExecutionHandle
    result: TaskResult | None = None
    error: ExecutorError | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.error is None):
            raise ValueError("AttemptCompletion requires exactly one of result or error")

    @property
    def succeeded(self) -> bool:
        return self.result is not None


class CompletionQueue:
    """Thread-safe FIFO transfer of terminal attempt completions."""

    def __init__(self) -> None:
        self._queue: Queue[AttemptCompletion] = Queue()

    def put(self, completion: AttemptCompletion) -> None:
        if not isinstance(completion, AttemptCompletion):
            raise TypeError("completion must be an AttemptCompletion")
        self._queue.put(completion)

    def get(self, *, timeout: float | None = None) -> AttemptCompletion:
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be greater than or equal to 0")
        return self._queue.get(timeout=timeout)

    def get_nowait(self) -> AttemptCompletion | None:
        try:
            return self._queue.get_nowait()
        except Empty:
            return None

    def drain(self) -> tuple[AttemptCompletion, ...]:
        completions: list[AttemptCompletion] = []
        while True:
            completion = self.get_nowait()
            if completion is None:
                return tuple(completions)
            completions.append(completion)

    def empty(self) -> bool:
        return self._queue.empty()

    def __len__(self) -> int:
        return self._queue.qsize()


__all__ = [
    "AttemptCompletion",
    "CompletionQueue",
    "ExecutionHandle",
]
