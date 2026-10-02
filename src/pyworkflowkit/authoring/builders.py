"""Mutable V2 authoring builder emitting immutable definitions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pyworkflowkit.authoring.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.authoring.io import InputDeclaration, OutputDeclaration
from pyworkflowkit.authoring.workloads import Workload
from pyworkflowkit.domain.enums import FailurePolicy
from pyworkflowkit.domain.values import RetryPolicy
from pyworkflowkit.policies.timeout import TimeoutPolicy
from pyworkflowkit.policies.trigger import TriggerRule


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
        return task

    def add(self, task: TaskDefinition) -> TaskDefinition:
        """Add an already-built canonical task definition."""

        if not isinstance(task, TaskDefinition):
            raise TypeError("task must be a TaskDefinition")
        if task.key in self._task_keys:
            raise ValueError(f"workflow builder already contains task key {task.key!r}")
        self._tasks.append(task)
        self._task_keys.add(task.key)
        return task

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
