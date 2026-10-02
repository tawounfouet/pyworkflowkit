"""Public immutable V2 ExecutionPlan model."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from pyworkflowkit.authoring import TaskDefinition
from pyworkflowkit.diagnostics import Diagnostic
from pyworkflowkit.domain.enums import FailurePolicy
from pyworkflowkit.policies import RetryPolicy, TimeoutPolicy, TriggerRule


@dataclass(frozen=True, slots=True)
class ExecutorRequirement:
    """Executor capability required by one planned task."""

    executor_key: str
    workload_kind: str
    portable: bool

    def __post_init__(self) -> None:
        for name, value in (
            ("executor_key", self.executor_key),
            ("workload_kind", self.workload_kind),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not isinstance(self.portable, bool):
            raise TypeError("portable must be a bool")

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "executor_key": self.executor_key,
            "workload_kind": self.workload_kind,
            "portable": self.portable,
        }


@dataclass(frozen=True, slots=True)
class TaskPlanEntry:
    """Resolved deterministic execution semantics for one task definition."""

    task: TaskDefinition
    position: int
    group_index: int
    executor_requirement: ExecutorRequirement
    required_integrations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.task, TaskDefinition):
            raise TypeError("task must be a V2 TaskDefinition")
        for name, value in (
            ("position", self.position),
            ("group_index", self.group_index),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be greater than or equal to 0")
        if not isinstance(self.executor_requirement, ExecutorRequirement):
            raise TypeError("executor_requirement must be an ExecutorRequirement")

        integrations = tuple(sorted(set(self.required_integrations)))
        for integration in integrations:
            if not isinstance(integration, str) or not integration.strip():
                raise ValueError("required integration names must not be empty")
        object.__setattr__(self, "required_integrations", integrations)

    @property
    def key(self) -> str:
        return self.task.key

    @property
    def dependencies(self) -> tuple[str, ...]:
        return self.task.dependencies

    @property
    def retry_policy(self) -> RetryPolicy:
        return self.task.retry_policy

    @property
    def timeout_policy(self) -> TimeoutPolicy:
        return self.task.timeout_policy

    @property
    def trigger_rule(self) -> TriggerRule:
        return self.task.trigger_rule

    @property
    def portable(self) -> bool:
        return self.executor_requirement.portable

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "task": self.task.fingerprint_payload(),
            "position": self.position,
            "group_index": self.group_index,
            "executor_requirement": self.executor_requirement.fingerprint_payload(),
            "required_integrations": list(self.required_integrations),
        }


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Public deterministic compiled representation of one workflow definition."""

    workflow_name: str
    workflow_version: str
    definition_fingerprint: str
    failure_policy: FailurePolicy
    tasks: tuple[TaskPlanEntry, ...]
    topological_order: tuple[str, ...]
    groups: tuple[tuple[str, ...], ...]
    required_capabilities: tuple[str, ...] = ()
    required_integrations: tuple[str, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("workflow_name", self.workflow_name),
            ("workflow_version", self.workflow_version),
            ("definition_fingerprint", self.definition_fingerprint),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not isinstance(self.failure_policy, FailurePolicy):
            raise TypeError("failure_policy must be a FailurePolicy")

        tasks = tuple(self.tasks)
        if not tasks:
            raise ValueError("ExecutionPlan must contain at least one task")

        keys = tuple(task.key for task in tasks)
        if len(keys) != len(set(keys)):
            raise ValueError("ExecutionPlan task keys must be unique")

        expected_positions = tuple(range(len(tasks)))
        if tuple(task.position for task in tasks) != expected_positions:
            raise ValueError("ExecutionPlan task positions must be contiguous from zero")

        order = tuple(self.topological_order)
        if order != keys:
            raise ValueError("ExecutionPlan task order must match topological_order exactly")

        groups = tuple(tuple(group) for group in self.groups)
        flattened = tuple(task_key for group in groups for task_key in group)
        if flattened != order:
            raise ValueError("ExecutionPlan groups must flatten to topological_order")

        by_key = {task.key: task for task in tasks}
        for group_index, group in enumerate(groups):
            for task_key in group:
                if by_key[task_key].group_index != group_index:
                    raise ValueError(f"task {task_key!r} has inconsistent group_index")

        capabilities = tuple(sorted(set(self.required_capabilities)))
        integrations = tuple(sorted(set(self.required_integrations)))
        diagnostics = tuple(self.diagnostics)
        if not all(isinstance(item, Diagnostic) for item in diagnostics):
            raise TypeError("diagnostics must contain only Diagnostic values")

        object.__setattr__(self, "tasks", tasks)
        object.__setattr__(self, "topological_order", order)
        object.__setattr__(self, "groups", groups)
        object.__setattr__(self, "required_capabilities", capabilities)
        object.__setattr__(self, "required_integrations", integrations)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def portable(self) -> bool:
        return all(task.portable for task in self.tasks)

    def task(self, key: str) -> TaskPlanEntry:
        for task in self.tasks:
            if task.key == key:
                return task
        raise KeyError(key)

    def fingerprint(self) -> str:
        payload = {
            "workflow_name": self.workflow_name,
            "workflow_version": self.workflow_version,
            "definition_fingerprint": self.definition_fingerprint,
            "failure_policy": self.failure_policy.value,
            "tasks": [task.fingerprint_payload() for task in self.tasks],
            "topological_order": list(self.topological_order),
            "groups": [list(group) for group in self.groups],
            "required_capabilities": list(self.required_capabilities),
            "required_integrations": list(self.required_integrations),
            "diagnostics": [
                {
                    "code": diagnostic.code,
                    "severity": diagnostic.severity.value,
                    "summary": diagnostic.summary,
                    "details": [list(item) for item in diagnostic.details],
                    "decision_context": diagnostic.decision_context,
                    "related_policy": diagnostic.related_policy,
                }
                for diagnostic in self.diagnostics
            ],
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
        lines = [
            (f"ExecutionPlan(workflow={self.workflow_name!r}, version={self.workflow_version!r})"),
            f"definition_fingerprint={self.definition_fingerprint}",
            f"plan_fingerprint={self.fingerprint()}",
            f"portable={str(self.portable).lower()}",
            "topological_order=" + " -> ".join(self.topological_order),
        ]
        for task in self.tasks:
            dependencies = ", ".join(task.dependencies) or "-"
            integrations = ", ".join(task.required_integrations) or "-"
            lines.append(
                f"- {task.key}: group={task.group_index}, "
                f"depends_on=[{dependencies}], "
                f"executor={task.executor_requirement.executor_key}, "
                f"integrations=[{integrations}]"
            )
        return "\n".join(lines)


__all__ = [
    "ExecutionPlan",
    "ExecutorRequirement",
    "TaskPlanEntry",
]
