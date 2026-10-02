"""Canonical immutable PyWorkflowKit V2 authoring definitions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from pyworkflowkit.authoring._values import (
    FrozenJsonValue,
    freeze_metadata,
    require_non_empty_text,
    thaw_json_value,
)
from pyworkflowkit.authoring.io import InputDeclaration, OutputDeclaration
from pyworkflowkit.authoring.workloads import (
    Workload,
    WorkloadDescriptor,
    workload_fingerprint_payload,
    workload_portability,
)
from pyworkflowkit.domain.enums import FailurePolicy
from pyworkflowkit.domain.values import RetryPolicy
from pyworkflowkit.policies.timeout import TimeoutPolicy
from pyworkflowkit.policies.trigger import TriggerRule


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    """Immutable declaration of exactly one workload boundary."""

    key: str
    workload: Workload
    dependencies: tuple[str, ...] = ()
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    timeout_policy: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    trigger_rule: TriggerRule = TriggerRule.ALL_SUCCESS
    inputs: tuple[InputDeclaration, ...] = ()
    outputs: tuple[OutputDeclaration, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.key, field_name="task key")
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
                "delay_seconds": self.retry_policy.delay_seconds,
                "max_delay_seconds": self.retry_policy.max_delay_seconds,
                "retryable_error_categories": sorted(
                    self.retry_policy.retryable_error_categories
                ),
            },
            "timeout_policy": {
                "execution_timeout": self.timeout_policy.execution_timeout,
            },
            "trigger_rule": self.trigger_rule.value,
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
    ) -> "WorkflowDefinitionBuilder":
        """Create a mutable authoring helper for one immutable definition."""

        from pyworkflowkit.authoring.builders import WorkflowDefinitionBuilder

        return WorkflowDefinitionBuilder(
            name=name,
            version=version,
            failure_policy=failure_policy,
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
                    raise ValueError(
                        f"task {task.key!r} depends on unknown task {dependency!r}"
                    )
        _validate_acyclic(self.tasks)

    def fingerprint(self) -> str:
        """Return deterministic SHA-256 fingerprint of authoring semantics."""

        payload = {
            "name": self.name,
            "version": self.version,
            "failure_policy": self.failure_policy.value,
            "tasks": [
                task.fingerprint_payload()
                for task in sorted(self.tasks, key=lambda item: item.key)
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
        name = getattr(value, "name")
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
            if not dependencies[downstream] and downstream not in visited and downstream not in ready:
                ready.append(downstream)
                ready.sort()

    if len(visited) != len(tasks):
        cyclic = sorted(key for key, upstream in dependencies.items() if upstream)
        raise ValueError(
            "workflow dependency topology contains a cycle involving: "
            + ", ".join(cyclic)
        )


def _metadata_payload(metadata: Mapping[str, object]) -> dict[str, object]:
    from typing import cast

    return {
        key: thaw_json_value(cast(FrozenJsonValue, metadata[key]))
        for key in sorted(metadata)
    }


def _canonicalize(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize(value[key])
            for key in sorted(value, key=str)
        }
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    raise TypeError(
        "workload fingerprint payload must contain only JSON-compatible values; "
        f"got {type(value).__name__}"
    )


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyworkflowkit.authoring.builders import WorkflowDefinitionBuilder


__all__ = ["TaskDefinition", "WorkflowDefinition"]
