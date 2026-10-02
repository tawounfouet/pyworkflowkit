"""Internal deterministic V2 task-readiness decisions."""

from __future__ import annotations

from dataclasses import dataclass

from pyworkflowkit.planning import TaskPlanEntry
from pyworkflowkit.policies import TriggerRule
from pyworkflowkit.states import SkipReason, TaskRunStatus
from pyworkflowkit.states.enums import TASK_RUN_TERMINAL_STATUSES


@dataclass(frozen=True, slots=True)
class _ReadinessDecision:
    ready: bool
    skip_reason: SkipReason | None = None


def evaluate_readiness(
    entry: TaskPlanEntry,
    *,
    statuses: dict[str, TaskRunStatus],
) -> _ReadinessDecision:
    upstream = tuple(statuses[key] for key in entry.dependencies)
    if not all(status in TASK_RUN_TERMINAL_STATUSES for status in upstream):
        return _ReadinessDecision(ready=False)

    rule = entry.trigger_rule
    if rule is TriggerRule.ALWAYS:
        allowed = True
    elif rule is TriggerRule.ALL_SUCCESS:
        allowed = all(status is TaskRunStatus.SUCCEEDED for status in upstream)
    elif rule is TriggerRule.ALL_DONE:
        allowed = True
    elif rule is TriggerRule.ANY_SUCCESS:
        allowed = any(status is TaskRunStatus.SUCCEEDED for status in upstream)
    elif rule is TriggerRule.ANY_FAILED:
        allowed = any(
            status in {TaskRunStatus.FAILED, TaskRunStatus.TIMED_OUT} for status in upstream
        )
    elif rule is TriggerRule.NONE_FAILED:
        allowed = not any(
            status in {TaskRunStatus.FAILED, TaskRunStatus.TIMED_OUT} for status in upstream
        )
    else:  # pragma: no cover - enum exhaustiveness guard
        raise RuntimeError(f"unsupported TriggerRule {rule!r}")

    if allowed:
        return _ReadinessDecision(ready=True)
    return _ReadinessDecision(
        ready=False,
        skip_reason=SkipReason.TRIGGER_RULE_UNSATISFIED,
    )


def descendants_of(task_key: str, entries: tuple[TaskPlanEntry, ...]) -> frozenset[str]:
    downstream: dict[str, set[str]] = {entry.key: set() for entry in entries}
    for entry in entries:
        for dependency in entry.dependencies:
            downstream[dependency].add(entry.key)

    discovered: set[str] = set()
    pending = list(downstream[task_key])
    while pending:
        candidate = pending.pop()
        if candidate in discovered:
            continue
        discovered.add(candidate)
        pending.extend(downstream[candidate])
    return frozenset(discovered)


__all__: list[str] = []
