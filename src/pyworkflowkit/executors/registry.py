"""Canonical V2 executor registry."""

from __future__ import annotations

from collections.abc import Iterable

from pyworkflowkit.errors import ExecutorNotFoundError
from pyworkflowkit.executors.contracts import Executor, ExecutorDescriptor


class ExecutorRegistry:
    """Explicit executor-id to Executor mapping for V2 runtime composition."""

    def __init__(self, executors: Iterable[Executor] = ()) -> None:
        self._executors: dict[str, Executor] = {}
        for executor in executors:
            self.register(executor)

    def register(self, executor: Executor) -> None:
        if not isinstance(executor, Executor):
            raise TypeError("executor must satisfy the V2 Executor Protocol")
        executor_id = executor.descriptor.executor_id
        existing = self._executors.get(executor_id)
        if existing is executor:
            return
        if existing is not None:
            raise ValueError(f"executor {executor_id!r} is already registered")
        self._executors[executor_id] = executor

    def resolve(self, executor_id: str) -> Executor:
        if not isinstance(executor_id, str) or not executor_id.strip():
            raise ValueError("executor_id must not be empty")
        try:
            return self._executors[executor_id]
        except KeyError as exc:
            raise ExecutorNotFoundError(executor_key=executor_id) from exc

    def descriptors(self) -> tuple[ExecutorDescriptor, ...]:
        return tuple(
            self._executors[key].descriptor
            for key in sorted(self._executors)
        )

    @property
    def executor_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._executors))

    def __contains__(self, executor_id: object) -> bool:
        return isinstance(executor_id, str) and executor_id in self._executors


__all__ = ["ExecutorRegistry"]
