"""Authoring validation, cycle detection, and dependency graph tracking."""

from __future__ import annotations

import weakref
from collections import deque
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from pyworkflowkit.domain.ids import TaskId
from pyworkflowkit.errors import CycleDetectedError

if TYPE_CHECKING:
    from pyworkflowkit.authoring.definitions import TaskDefinition


class CircularDependencyError(CycleDetectedError, ValueError):
    """Raised immediately when a dependency introduces a directed cycle."""

    def __init__(
        self,
        cycle_path: Sequence[str] | None = None,
        *,
        task_ids: Iterable[TaskId] | None = None,
    ) -> None:
        if cycle_path is not None:
            self.cycle_path = tuple(cycle_path)
            rendered = " -> ".join(self.cycle_path)
            task_ids_arg: tuple[TaskId, ...] = tuple(TaskId(k) for k in self.cycle_path)
            super().__init__(task_ids=task_ids_arg)
            super(CycleDetectedError, self).__init__(
                f"Cycle detected: {rendered} (workflow dependency topology contains a cycle)"
            )
        elif task_ids is not None:
            t_ids = tuple(task_ids)
            self.cycle_path = tuple(str(k) for k in t_ids)
            super().__init__(task_ids=t_ids)
        else:
            self.cycle_path = ()
            super().__init__(task_ids=())


# Global tracking of active authoring task dependencies using object IDs and weak references
_UPSTREAM_MAP: dict[int, set[int]] = {}
_TASK_MAP: dict[int, weakref.ref[Any]] = {}


def _cleanup_task(task_id: int) -> None:
    _UPSTREAM_MAP.pop(task_id, None)
    _TASK_MAP.pop(task_id, None)
    for upstreams in _UPSTREAM_MAP.values():
        upstreams.discard(task_id)


def register_authoring_task(task: TaskDefinition) -> None:
    """Register an authoring task definition for dependency tracking."""
    tid = id(task)
    if tid not in _TASK_MAP:
        _TASK_MAP[tid] = weakref.ref(task)
        _UPSTREAM_MAP[tid] = set()
        weakref.finalize(task, _cleanup_task, tid)


def _find_path(from_id: int, to_id: int) -> list[int] | None:
    """Find a directed path from `from_id` to `to_id` following upstream dependencies."""
    queue: deque[list[int]] = deque([[from_id]])
    visited: set[int] = {from_id}

    while queue:
        path = queue.popleft()
        current = path[-1]
        if current == to_id:
            return path

        for upstream in _UPSTREAM_MAP.get(current, ()):
            if upstream not in visited:
                visited.add(upstream)
                queue.append(path + [upstream])

    return None


def add_authoring_dependency(upstream: TaskDefinition, downstream: TaskDefinition) -> None:
    """Declare that `downstream` depends on `upstream` (upstream >> downstream).

    Raises:
        CircularDependencyError: if this dependency introduces a cycle.
    """
    if upstream.key == downstream.key or upstream is downstream:
        raise CircularDependencyError([upstream.key, downstream.key])

    register_authoring_task(upstream)
    register_authoring_task(downstream)

    uid = id(upstream)
    did = id(downstream)

    # Check if upstream already depends on downstream (i.e. path from upstream to downstream)
    path = _find_path(uid, did)
    if path is not None:
        # A path already exists from upstream to downstream:
        # downstream -> ... -> upstream.
        # Adding upstream -> downstream closes the cycle!
        cycle_keys: list[str] = []
        for tid in reversed(path):
            t_ref = _TASK_MAP.get(tid)
            t_obj = t_ref() if t_ref is not None else None
            key = t_obj.key if t_obj is not None else str(tid)
            cycle_keys.append(key)
        # Close cycle with the target
        cycle_keys.append(downstream.key)
        raise CircularDependencyError(cycle_keys)

    # Add the dependency
    _UPSTREAM_MAP[did].add(uid)
    if upstream.key not in downstream.dependencies:
        new_deps = tuple(sorted(set(downstream.dependencies + (upstream.key,))))
        object.__setattr__(downstream, "dependencies", new_deps)


__all__ = [
    "CircularDependencyError",
    "add_authoring_dependency",
    "register_authoring_task",
]
