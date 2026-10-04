"""Canonical immutable PyWorkflowKit V2 authoring definitions."""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, cast, overload

if sys.version_info >= (3, 13):
    from typing import TypeVar
else:  # pragma: no cover
    from typing_extensions import TypeVar

from pyworkflowkit.authoring._values import (
    FrozenJsonValue,
    freeze_metadata,
    require_non_empty_text,
    thaw_json_value,
)
from pyworkflowkit.authoring.io import InputDeclaration, OutputDeclaration
from pyworkflowkit.authoring.validation import (
    CircularDependencyError,
    add_authoring_dependency,
    register_authoring_task,
)
from pyworkflowkit.authoring.workloads import (
    Workload,
    WorkloadDescriptor,
    WorkloadPortability,
    workload_fingerprint_payload,
    workload_portability,
)
from pyworkflowkit.domain.enums import FailurePolicy
from pyworkflowkit.domain.ids import TaskId
from pyworkflowkit.policies.retry import RetryPolicy
from pyworkflowkit.policies.timeout import TimeoutPolicy
from pyworkflowkit.policies.trigger import TriggerRule

T_Input = TypeVar("T_Input", default=Any)
T_Output = TypeVar("T_Output", default=Any)


@dataclass(frozen=True, slots=True, weakref_slot=True)
class TaskDefinition(Generic[T_Input, T_Output]):
    """Immutable declaration of exactly one workload boundary."""

    key: str
    workload: Workload
    dependencies: tuple[str, ...] = ()
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_policy: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    trigger_rule: TriggerRule = TriggerRule.ALL_SUCCESS
    is_deterministic: bool = True
    inputs: tuple[InputDeclaration, ...] = ()
    outputs: tuple[OutputDeclaration, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.key, field_name="task key")
        if not isinstance(self.is_deterministic, bool):
            raise TypeError("is_deterministic must be a bool")
        if not callable(self.workload) and not isinstance(self.workload, WorkloadDescriptor):
            raise TypeError("workload must be callable or implement WorkloadDescriptor")

        dependencies = tuple(self.dependencies)
        if len(dependencies) != len(set(dependencies)):
            raise ValueError(f"task {self.key!r} declares duplicate dependencies")
        for dependency in dependencies:
            require_non_empty_text(dependency, field_name="dependency key")
        if self.key in dependencies:
            raise ValueError(f"task {self.key!r} cannot depend on itself")

        if not isinstance(self.retry_policy, RetryPolicy):
            raise TypeError("retry_policy must be a RetryPolicy")
        if not isinstance(self.timeout_policy, TimeoutPolicy):
            raise TypeError("timeout_policy must be a TimeoutPolicy")
        if not isinstance(self.trigger_rule, TriggerRule):
            raise TypeError("trigger_rule must be a TriggerRule")

        inputs = tuple(self.inputs)
        outputs = tuple(self.outputs)
        _validate_named_declarations(inputs, InputDeclaration, kind="input")
        _validate_named_declarations(outputs, OutputDeclaration, kind="output")

        object.__setattr__(self, "dependencies", dependencies)
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(self, "outputs", outputs)
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
        register_authoring_task(self)

    def __rshift__(
        self,
        other: TaskDefinition[Any, Any] | Sequence[TaskDefinition[Any, Any]],
    ) -> TaskDefinition[Any, Any] | TaskSequence:
        """Declare that `other` depends on `self` (self >> other)."""
        if isinstance(other, TaskDefinition):
            add_authoring_dependency(self, other)
            return other
        if isinstance(other, Sequence):
            if any(not isinstance(item, TaskDefinition) for item in other):
                return NotImplemented
            for item in other:
                add_authoring_dependency(self, item)
            return TaskSequence(other)
        return NotImplemented

    def __rrshift__(
        self,
        other: Sequence[TaskDefinition[Any, Any]],
    ) -> TaskDefinition[T_Input, T_Output]:
        """Support fan-in: [task_a, task_b] >> self."""
        if isinstance(other, Sequence):
            if any(not isinstance(item, TaskDefinition) for item in other):
                return NotImplemented
            for item in other:
                add_authoring_dependency(item, self)
            return self
        return NotImplemented

    def __lshift__(
        self,
        other: TaskDefinition[Any, Any] | Sequence[TaskDefinition[Any, Any]],
    ) -> TaskDefinition[T_Input, T_Output]:
        """Declare that `self` depends on `other` (self << other)."""
        if isinstance(other, TaskDefinition):
            add_authoring_dependency(other, self)
            return self
        if isinstance(other, Sequence):
            if any(not isinstance(item, TaskDefinition) for item in other):
                return NotImplemented
            for item in other:
                add_authoring_dependency(item, self)
            return self
        return NotImplemented

    def __rlshift__(
        self,
        other: Sequence[TaskDefinition[Any, Any]],
    ) -> TaskSequence:
        """Support fan-out reverse: [task_a, task_b] << self."""
        if isinstance(other, Sequence):
            if any(not isinstance(item, TaskDefinition) for item in other):
                return NotImplemented
            for item in other:
                add_authoring_dependency(self, item)
            return TaskSequence(other)
        return NotImplemented

    @property
    def portable(self) -> bool:
        """Whether the workload declaration itself is durable/portable."""

        return workload_portability(self.workload).value == "portable"

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "key": self.key,
            "workload": _canonicalize(workload_fingerprint_payload(self.workload)),
            "dependencies": sorted(self.dependencies),
            "retry_policy": {
                "max_attempts": self.retry_policy.max_attempts,
                "backoff_strategy": self.retry_policy.backoff_strategy.value,
                "initial_delay_seconds": self.retry_policy.initial_delay_seconds,
                "max_delay_seconds": self.retry_policy.max_delay_seconds,
                "jitter": self.retry_policy.jitter.value,
                "retryable_failure_categories": sorted(
                    category.value for category in self.retry_policy.retryable_failure_categories
                ),
                "total_budget_seconds": self.retry_policy.total_budget_seconds,
                "reconciliation_required": self.retry_policy.reconciliation_required,
            },
            "timeout_policy": {
                "execution_timeout": self.timeout_policy.execution_timeout,
            },
            "trigger_rule": self.trigger_rule.value,
            "is_deterministic": self.is_deterministic,
            "inputs": [
                declaration.fingerprint_payload()
                for declaration in sorted(self.inputs, key=lambda item: item.name)
            ],
            "outputs": [
                declaration.fingerprint_payload()
                for declaration in sorted(self.outputs, key=lambda item: item.name)
            ],
            "metadata": _metadata_payload(self.metadata),
        }


class TaskSequence(Sequence[TaskDefinition[Any, Any]]):
    """Immutable sequence of TaskDefinition instances supporting flow operators."""

    __slots__ = ("_tasks",)

    def __init__(self, tasks: Iterable[TaskDefinition[Any, Any]]) -> None:
        self._tasks: tuple[TaskDefinition[Any, Any], ...] = tuple(tasks)

    def __len__(self) -> int:
        return len(self._tasks)

    @overload
    def __getitem__(self, index: int) -> TaskDefinition[Any, Any]: ...

    @overload
    def __getitem__(self, index: slice) -> TaskSequence: ...

    def __getitem__(self, index: int | slice) -> TaskDefinition[Any, Any] | TaskSequence:
        if isinstance(index, slice):
            return TaskSequence(self._tasks[index])
        return self._tasks[index]

    def __iter__(self) -> Iterator[TaskDefinition[Any, Any]]:
        return iter(self._tasks)

    def __rshift__(
        self,
        other: TaskDefinition[Any, Any] | Sequence[TaskDefinition[Any, Any]],
    ) -> TaskDefinition[Any, Any] | TaskSequence:
        if isinstance(other, TaskDefinition):
            for task in self._tasks:
                add_authoring_dependency(task, other)
            return other
        if isinstance(other, Sequence):
            if any(not isinstance(item, TaskDefinition) for item in other):
                return NotImplemented
            for task in self._tasks:
                for item in other:
                    add_authoring_dependency(task, item)
            return TaskSequence(other)
        return NotImplemented

    def __lshift__(
        self,
        other: TaskDefinition[Any, Any] | Sequence[TaskDefinition[Any, Any]],
    ) -> TaskSequence:
        if isinstance(other, TaskDefinition):
            for task in self._tasks:
                add_authoring_dependency(other, task)
            return self
        if isinstance(other, Sequence):
            if any(not isinstance(item, TaskDefinition) for item in other):
                return NotImplemented
            for item in other:
                for task in self._tasks:
                    add_authoring_dependency(item, task)
            return self
        return NotImplemented

    def __repr__(self) -> str:
        return f"TaskSequence({[t.key for t in self._tasks]!r})"


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """Immutable canonical root for PyWorkflowKit V2 authoring."""

    name: str
    tasks: tuple[TaskDefinition, ...]
    version: str = "1"
    failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.name, field_name="workflow name")
        require_non_empty_text(self.version, field_name="workflow version")
        if not isinstance(self.failure_policy, FailurePolicy):
            raise TypeError("failure_policy must be a FailurePolicy")

        tasks = tuple(self.tasks)
        if not tasks:
            raise ValueError("workflow must contain at least one task")

        task_keys: set[str] = set()
        for task in tasks:
            if not isinstance(task, TaskDefinition):
                raise TypeError("tasks must contain only TaskDefinition values")
            if task.key in task_keys:
                raise ValueError(f"workflow declares duplicate task key {task.key!r}")
            task_keys.add(task.key)

        object.__setattr__(self, "tasks", tasks)
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))
        self.validate()

    @classmethod
    def builder(
        cls,
        *,
        name: str,
        version: str = "1",
        failure_policy: FailurePolicy = FailurePolicy.FAIL_FAST,
        metadata: Mapping[str, object] | None = None,
    ) -> WorkflowDefinitionBuilder:
        """Create a mutable authoring helper for one immutable definition."""

        from pyworkflowkit.authoring.builders import WorkflowDefinitionBuilder

        return WorkflowDefinitionBuilder(
            name=name,
            version=version,
            failure_policy=failure_policy,
            metadata=metadata or {},
        )

    @property
    def workload_kind(self) -> str:
        """Stable workload category as a composite workflow descriptor."""
        return "workflow"

    @property
    def portability(self) -> WorkloadPortability:
        """Whether the sub-workflow descriptor is portable."""
        return (
            WorkloadPortability.PORTABLE
            if all(t.portable for t in self.tasks)
            else WorkloadPortability.LOCAL_ONLY
        )

    def fingerprint_payload(self) -> Mapping[str, object]:
        """Return deterministic workload identity for composite sub-workflows."""
        return {
            "kind": self.workload_kind,
            "name": self.name,
            "version": self.version,
            "fingerprint": self.fingerprint(),
            "portability": self.portability.value,
        }

    def as_task(
        self,
        key: str,
        *,
        depends_on: Sequence[TaskDefinition[Any, Any] | str] = (),
        retry_policy: RetryPolicy | None = None,
        timeout_policy: TimeoutPolicy | None = None,
        trigger_rule: TriggerRule = TriggerRule.ALL_SUCCESS,
        is_deterministic: bool = True,
        inputs: Sequence[InputDeclaration] = (),
        outputs: Sequence[OutputDeclaration] = (),
        metadata: Mapping[str, object] | None = None,
    ) -> TaskDefinition[Any, Any]:
        """Convert this workflow into a composite task usable in parent workflows."""
        dependencies = tuple(d.key if isinstance(d, TaskDefinition) else str(d) for d in depends_on)
        return TaskDefinition(
            key=key,
            workload=self,
            dependencies=dependencies,
            retry_policy=retry_policy or RetryPolicy(),
            timeout_policy=timeout_policy or TimeoutPolicy(),
            trigger_rule=trigger_rule,
            is_deterministic=is_deterministic,
            inputs=tuple(inputs),
            outputs=tuple(outputs),
            metadata=metadata or {},
        )

    def task(self, key: str) -> TaskDefinition:
        """Return one task by authoring key."""

        for task in self.tasks:
            if task.key == key:
                return task
        raise KeyError(key)

    def validate(self) -> None:
        """Validate declared topology without executing workload code."""

        known = {task.key for task in self.tasks}
        for task in self.tasks:
            for dependency in task.dependencies:
                if dependency not in known:
                    raise ValueError(f"task {task.key!r} depends on unknown task {dependency!r}")
        _validate_acyclic(self.tasks)

    def fingerprint(self) -> str:
        """Return deterministic SHA-256 fingerprint of authoring semantics."""

        payload = {
            "name": self.name,
            "version": self.version,
            "failure_policy": self.failure_policy.value,
            "tasks": [
                task.fingerprint_payload() for task in sorted(self.tasks, key=lambda item: item.key)
            ],
            "metadata": _metadata_payload(self.metadata),
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"

    def explain(self) -> str:
        """Return deterministic human-readable authoring inspection."""

        lines = [
            f"WorkflowDefinition(name={self.name!r}, version={self.version!r})",
            f"fingerprint={self.fingerprint()}",
        ]
        for task in sorted(self.tasks, key=lambda item: item.key):
            dependencies = ", ".join(sorted(task.dependencies)) or "-"
            lines.append(
                f"- {task.key}: depends_on=[{dependencies}], "
                f"trigger={task.trigger_rule.value}, portable={str(task.portable).lower()}"
            )
        return "\n".join(lines)


def _validate_named_declarations(
    values: tuple[object, ...],
    expected_type: type[object],
    *,
    kind: str,
) -> None:
    names: set[str] = set()
    for value in values:
        if not isinstance(value, expected_type):
            raise TypeError(f"{kind}s must contain only {expected_type.__name__} values")
        name = cast(InputDeclaration | OutputDeclaration, value).name
        if name in names:
            raise ValueError(f"task declares duplicate {kind} {name!r}")
        names.add(name)


def _validate_acyclic(tasks: tuple[TaskDefinition, ...]) -> None:
    dependencies = {task.key: set(task.dependencies) for task in tasks}
    ready = sorted(key for key, upstream in dependencies.items() if not upstream)
    visited: list[str] = []

    while ready:
        key = ready.pop(0)
        visited.append(key)
        for downstream in sorted(dependencies):
            if key not in dependencies[downstream]:
                continue
            dependencies[downstream].remove(key)
            if (
                not dependencies[downstream]
                and downstream not in visited
                and downstream not in ready
            ):
                ready.append(downstream)
                ready.sort()

    if len(visited) != len(tasks):
        cyclic = sorted(key for key, upstream in dependencies.items() if upstream)
        raise CircularDependencyError(
            cyclic,
            task_ids=[TaskId(k) for k in cyclic],
        )


def _metadata_payload(metadata: Mapping[str, object]) -> dict[str, object]:
    from typing import cast

    return {key: thaw_json_value(cast(FrozenJsonValue, metadata[key])) for key in sorted(metadata)}


def _canonicalize(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _canonicalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    raise TypeError(
        "workload fingerprint payload must contain only JSON-compatible values; "
        f"got {type(value).__name__}"
    )


if TYPE_CHECKING:
    from pyworkflowkit.authoring.builders import WorkflowDefinitionBuilder


__all__ = ["TaskDefinition", "TaskSequence", "WorkflowDefinition"]
