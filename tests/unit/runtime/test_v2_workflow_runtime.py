"""LOT-06 unit tests for the canonical V2 WorkflowRuntime."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit.authoring import RegisteredWorkload, TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.values import RetryPolicy
from pyworkflowkit.errors import RuntimeInvariantError
from pyworkflowkit.executors import InlineExecutor, TaskExecutionContext
from pyworkflowkit.persistence import InMemoryMetadataStore, StateEntityType
from pyworkflowkit.planning import WorkflowPlanner
from pyworkflowkit.policies import TimeoutPolicy, TriggerRule
from pyworkflowkit.runtime import (
    CorrelationId,
    RuntimeIdentityFactory,
    TaskAttemptId,
    TaskRunId,
    WorkflowResult,
    WorkflowRunId,
    WorkflowRuntime,
)
from pyworkflowkit.states import (
    SkipReason,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)


class SteppingClock:
    def __init__(self) -> None:
        self._value = datetime(2026, 10, 2, 14, 30, tzinfo=UTC)

    def now(self) -> datetime:
        current = self._value
        self._value += timedelta(milliseconds=1)
        return current


class FixedIdentityFactory:
    def __init__(self) -> None:
        self._workflow = 0
        self._task = 0
        self._attempt = 0
        self._correlation = 0

    def new_workflow_run_id(self) -> WorkflowRunId:
        self._workflow += 1
        return WorkflowRunId.parse(f"W-{self._workflow}")

    def new_task_run_id(self) -> TaskRunId:
        self._task += 1
        return TaskRunId.parse(f"TR-{self._task}")

    def new_task_attempt_id(self) -> TaskAttemptId:
        self._attempt += 1
        return TaskAttemptId.parse(f"TA-{self._attempt}")

    def new_correlation_id(self) -> CorrelationId:
        self._correlation += 1
        return CorrelationId.parse(f"C-{self._correlation}")


def _runtime(
    store: InMemoryMetadataStore,
    *,
    executor: InlineExecutor | None = None,
) -> WorkflowRuntime:
    identity_factory = FixedIdentityFactory()
    assert isinstance(identity_factory, RuntimeIdentityFactory)
    return WorkflowRuntime(
        executor=executor or InlineExecutor(),
        metadata=store,
        clock=SteppingClock(),
        identity_factory=identity_factory,
    )


def test_local_dag_executes_end_to_end_and_passes_dependency_outputs() -> None:
    store = InMemoryMetadataStore()

    def extract() -> int:
        return 21

    def transform(context: TaskExecutionContext) -> int:
        return int(context.dependency_outputs["extract"]) * 2

    workflow = WorkflowDefinition(
        name="demo",
        tasks=(
            TaskDefinition(key="extract", workload=extract),
            TaskDefinition(
                key="transform",
                workload=transform,
                dependencies=("extract",),
            ),
        ),
    )

    result = _runtime(store).run(workflow)

    assert isinstance(result, WorkflowResult)
    assert result.run_id == WorkflowRunId.parse("W-1")
    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert result.task("extract").status is TaskRunStatus.SUCCEEDED
    assert result.task("extract").output == 21
    assert result.task("transform").output == 42
    assert len(result.task("extract").attempt_ids) == 1
    assert len(result.task("transform").attempt_ids) == 1

    persisted = store.get_workflow_run(result.run_id)
    assert persisted.status is WorkflowRunStatus.SUCCEEDED
    assert all(
        task.status is TaskRunStatus.SUCCEEDED for task in store.list_task_runs(result.run_id)
    )
    assert all(
        attempts[0].status is TaskAttemptStatus.SUCCEEDED
        for task in store.list_task_runs(result.run_id)
        if (attempts := store.list_task_attempts(task.task_run_id))
    )


def test_runtime_accepts_precompiled_execution_plan() -> None:
    store = InMemoryMetadataStore()
    workflow = WorkflowDefinition(
        name="compiled",
        tasks=(TaskDefinition(key="one", workload=lambda: "ok"),),
    )
    plan = WorkflowPlanner().compile(workflow)

    result = _runtime(store).run(plan)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert store.get_workflow_run(result.run_id).plan_fingerprint == plan.fingerprint()


def test_registered_workload_executes_through_explicit_inline_binding() -> None:
    store = InMemoryMetadataStore()

    def bound(context: TaskExecutionContext) -> str:
        return context.workload_parameters["value"]

    workflow = WorkflowDefinition(
        name="registered",
        tasks=(
            TaskDefinition(
                key="registered",
                workload=RegisteredWorkload(
                    "jobs.registered",
                    parameters=(("value", "resolved"),),
                ),
            ),
        ),
    )

    result = _runtime(
        store,
        executor=InlineExecutor({"jobs.registered": bound}),
    ).run(workflow)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert result.task("registered").output == "resolved"


def test_fail_fast_marks_descendant_and_independent_tasks_with_distinct_skip_reasons() -> None:
    store = InMemoryMetadataStore()

    def fail() -> None:
        raise ValueError("expected failure")

    workflow = WorkflowDefinition(
        name="fail-fast",
        tasks=(
            TaskDefinition(key="a_fail", workload=fail),
            TaskDefinition(
                key="b_descendant",
                workload=lambda: None,
                dependencies=("a_fail",),
            ),
            TaskDefinition(key="c_independent", workload=lambda: None),
        ),
    )

    result = _runtime(store).run(workflow)

    assert result.status is WorkflowRunStatus.FAILED
    assert result.failure is not None
    assert result.failure.error_code == "ValueError"
    assert result.task("a_fail").status is TaskRunStatus.FAILED
    assert result.task("b_descendant").status is TaskRunStatus.SKIPPED
    assert result.task("c_independent").status is TaskRunStatus.SKIPPED

    by_key = {task.task_key: task for task in store.list_task_runs(result.run_id)}
    assert by_key["b_descendant"].skip_reason is SkipReason.DEPENDENCY_FAILED
    assert by_key["c_independent"].skip_reason is SkipReason.FAIL_FAST_ABORT
    assert store.list_task_attempts(by_key["b_descendant"].task_run_id) == ()
    assert store.list_task_attempts(by_key["c_independent"].task_run_id) == ()


def test_trigger_rule_can_skip_task_without_failing_workflow() -> None:
    store = InMemoryMetadataStore()
    workflow = WorkflowDefinition(
        name="trigger",
        tasks=(
            TaskDefinition(key="a", workload=lambda: "ok"),
            TaskDefinition(
                key="b",
                workload=lambda: "not-run",
                dependencies=("a",),
                trigger_rule=TriggerRule.ANY_FAILED,
            ),
        ),
    )

    result = _runtime(store).run(workflow)

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert result.task("a").status is TaskRunStatus.SUCCEEDED
    assert result.task("b").status is TaskRunStatus.SKIPPED

    task_b = next(task for task in store.list_task_runs(result.run_id) if task.task_key == "b")
    assert task_b.skip_reason is SkipReason.TRIGGER_RULE_UNSATISFIED
    assert store.list_task_attempts(task_b.task_run_id) == ()


def test_runtime_rejects_retry_policy_until_lot07_before_creating_run() -> None:
    store = InMemoryMetadataStore()
    workflow = WorkflowDefinition(
        name="retry-deferred",
        tasks=(
            TaskDefinition(
                key="a",
                workload=lambda: None,
                retry_policy=RetryPolicy(max_attempts=2),
            ),
        ),
    )

    with pytest.raises(RuntimeInvariantError, match="LOT-07"):
        _runtime(store).run(workflow)

    assert store.list_workflow_runs() == ()


def test_runtime_rejects_timeout_policy_until_lot08_before_creating_run() -> None:
    store = InMemoryMetadataStore()
    workflow = WorkflowDefinition(
        name="timeout-deferred",
        tasks=(
            TaskDefinition(
                key="a",
                workload=lambda: None,
                timeout_policy=TimeoutPolicy(execution_timeout=1.0),
            ),
        ),
    )

    with pytest.raises(RuntimeInvariantError, match="LOT-08"):
        _runtime(store).run(workflow)

    assert store.list_workflow_runs() == ()


def test_state_transition_history_is_basic_runtime_event_evidence() -> None:
    store = InMemoryMetadataStore()
    result = _runtime(store).run(
        WorkflowDefinition(
            name="events",
            tasks=(TaskDefinition(key="a", workload=lambda: 1),),
        )
    )

    workflow_history = store.list_state_transitions(
        entity_type=StateEntityType.WORKFLOW_RUN,
        entity_id=str(result.run_id),
    )
    assert tuple(item.to_status for item in workflow_history) == (
        "PENDING",
        "RUNNING",
        "SUCCEEDED",
    )

    task = store.list_task_runs(result.run_id)[0]
    task_history = store.list_state_transitions(
        entity_type=StateEntityType.TASK_RUN,
        entity_id=str(task.task_run_id),
    )
    assert tuple(item.to_status for item in task_history) == (
        "PENDING",
        "READY",
        "RUNNING",
        "SUCCEEDED",
    )


def test_workflow_result_is_immutable_projection_not_persisted_run() -> None:
    store = InMemoryMetadataStore()
    result = _runtime(store).run(
        WorkflowDefinition(
            name="result",
            tasks=(TaskDefinition(key="a", workload=lambda: 1),),
        )
    )

    with pytest.raises(FrozenInstanceError):
        result.status = WorkflowRunStatus.FAILED  # type: ignore[misc]
