"""Mutable V2 authoring builder emitting immutable definitions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pyworkflowkit.authoring.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.authoring.io import InputDeclaration, OutputDeclaration
from pyworkflowkit.authoring.validation import CircularDependencyError
from pyworkflowkit.authoring.workloads import Workload
from pyworkflowkit.domain.enums import FailurePolicy
from pyworkflowkit.policies.retry import RetryPolicy
from pyworkflowkit.policies.timeout import TimeoutPolicy
from pyworkflowkit.policies.trigger import TriggerRule


def _check_builder_cycles(tasks: Sequence[TaskDefinition]) -> None:
    known = {t.key for t in tasks}
    deps = {t.key: [d for d in t.dependencies if d in known] for t in tasks}
    visited: set[str] = set()
    rec_stack: list[str] = []

    def dfs(node: str) -> list[str] | None:
        visited.add(node)
        rec_stack.append(node)
        for neighbor in deps.get(node, []):
            if neighbor not in visited:
                cycle = dfs(neighbor)
                if cycle is not None:
                    return cycle
            elif neighbor in rec_stack:
                idx = rec_stack.index(neighbor)
                return rec_stack[idx:] + [neighbor]
        rec_stack.pop()
        return None

    for t in tasks:
        if t.key not in visited:
            cycle = dfs(t.key)
            if cycle is not None:
                raise CircularDependencyError(cycle)


class WorkflowDefinitionBuilder:
    """Mutable convenience layer around canonical immutable V2 definitions."""

    def __init__(
        self,
        *,
        name: str,
        version: str = "1",
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        self._name = name
        self._version = version
        self._failure_policy = failure_policy
        self._metadata = dict(metadata or {})
        self._tasks: list[TaskDefinition] = []
        self._task_keys: set[str] = set()

    def __enter__(self) -> WorkflowDefinitionBuilder:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    def task(
        self,
        key: str,
        *,
        workload: Workload,
        depends_on: Sequence[TaskDefinition | str] = (),
        retry_policy: RetryPolicy | None = None,
        timeout_policy: TimeoutPolicy | None = None,
        trigger_rule: TriggerRule = TriggerRule.ALL_SUCCESS,
        inputs: Sequence[InputDeclaration] = (),
        outputs: Sequence[OutputDeclaration] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> TaskDefinition:
        """Declare one task and return its canonical immutable definition."""

        if key in self._task_keys:
            raise ValueError(f"workflow builder already contains task key {key!r}")

        dependencies = tuple(
            value.key if isinstance(value, TaskDefinition) else value for value in depends_on
        )
        task = TaskDefinition(
            key=key,
            workload=workload,
            dependencies=dependencies,
            retry_policy=retry_policy or RetryPolicy(),
            timeout_policy=timeout_policy or TimeoutPolicy(),
            trigger_rule=trigger_rule,
            inputs=tuple(inputs),
            outputs=tuple(outputs),
            metadata=metadata or {},
        )
        self._tasks.append(task)
        self._task_keys.add(task.key)
        _check_builder_cycles(self._tasks)
        return task

    def add(self, task: TaskDefinition) -> TaskDefinition:
        """Add an already-built canonical task definition."""

        if not isinstance(task, TaskDefinition):
            raise TypeError("task must be a TaskDefinition")
        if task.key in self._task_keys:
            raise ValueError(f"workflow builder already contains task key {task.key!r}")
        self._tasks.append(task)
        self._task_keys.add(task.key)
        _check_builder_cycles(self._tasks)
        return task

    def add_task(self, task: TaskDefinition) -> TaskDefinition:
        """Alias for add()."""
        return self.add(task)

    def build(self) -> WorkflowDefinition:
        """Freeze current builder state into one canonical WorkflowDefinition."""

        return WorkflowDefinition(
            name=self._name,
            version=self._version,
            tasks=tuple(self._tasks),
            failure_policy=self._failure_policy,
            metadata=self._metadata,
        )


__all__ = ["WorkflowDefinitionBuilder"]
