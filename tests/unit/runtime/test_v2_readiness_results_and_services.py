"""Coverage and invariants for LOT-06 readiness, results and runtime services."""

from __future__ import annotations

from datetime import UTC

import pytest

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.diagnostics import Diagnostic, DiagnosticSeverity
from pyworkflowkit.planning import WorkflowPlanner
from pyworkflowkit.policies import TriggerRule
from pyworkflowkit.executors import CancellationStatus
from pyworkflowkit.runtime import (
    CancellationResult,
    CorrelationContext,
    CorrelationId,
    SystemClock,
    SystemRetryWaiter,
    TaskAttemptId,
    TaskOutcome,
    TaskRunId,
    UuidRuntimeIdentityFactory,
    WorkflowResult,
    WorkflowRunId,
)
from pyworkflowkit.runtime._readiness import descendants_of, evaluate_readiness
from pyworkflowkit.states import TaskRunStatus, WorkflowRunStatus


def _entry(trigger_rule: TriggerRule) -> object:
    workflow = WorkflowDefinition(
        name=f"ready-{trigger_rule.value}",
        tasks=(
            TaskDefinition(key="upstream", workload=lambda: None),
            TaskDefinition(
                key="target",
                workload=lambda: None,
                dependencies=("upstream",),
                trigger_rule=trigger_rule,
            ),
        ),
    )
    return WorkflowPlanner().compile(workflow).task("target")


@pytest.mark.parametrize(
    ("trigger_rule", "upstream_status", "ready"),
    [
        (TriggerRule.ALL_SUCCESS, TaskRunStatus.SUCCEEDED, True),
        (TriggerRule.ALL_SUCCESS, TaskRunStatus.FAILED, False),
        (TriggerRule.ALL_DONE, TaskRunStatus.FAILED, True),
        (TriggerRule.ANY_SUCCESS, TaskRunStatus.SUCCEEDED, True),
        (TriggerRule.ANY_SUCCESS, TaskRunStatus.FAILED, False),
        (TriggerRule.ANY_FAILED, TaskRunStatus.FAILED, True),
        (TriggerRule.ANY_FAILED, TaskRunStatus.SUCCEEDED, False),
        (TriggerRule.NONE_FAILED, TaskRunStatus.SUCCEEDED, True),
        (TriggerRule.NONE_FAILED, TaskRunStatus.FAILED, False),
        (TriggerRule.ALWAYS, TaskRunStatus.FAILED, True),
    ],
)
def test_readiness_trigger_rule_matrix(
    trigger_rule: TriggerRule,
    upstream_status: TaskRunStatus,
    ready: bool,
) -> None:
    entry = _entry(trigger_rule)
    decision = evaluate_readiness(  # type: ignore[arg-type]
        entry,
        statuses={"upstream": upstream_status},
    )

    assert decision.ready is ready
    assert (decision.skip_reason is None) is ready


def test_readiness_waits_for_non_terminal_dependency() -> None:
    entry = _entry(TriggerRule.ALL_DONE)
    decision = evaluate_readiness(  # type: ignore[arg-type]
        entry,
        statuses={"upstream": TaskRunStatus.RUNNING},
    )

    assert decision.ready is False
    assert decision.skip_reason is None


def test_descendants_are_transitive_and_exclude_independent_tasks() -> None:
    workflow = WorkflowDefinition(
        name="descendants",
        tasks=(
            TaskDefinition(key="a", workload=lambda: None),
            TaskDefinition(key="b", workload=lambda: None, dependencies=("a",)),
            TaskDefinition(key="c", workload=lambda: None, dependencies=("b",)),
            TaskDefinition(key="z", workload=lambda: None),
        ),
    )
    plan = WorkflowPlanner().compile(workflow)

    assert descendants_of("a", plan.tasks) == frozenset({"b", "c"})
    assert descendants_of("z", plan.tasks) == frozenset()


def _task_outcome(key: str = "task") -> TaskOutcome:
    return TaskOutcome(
        task_key=key,
        task_run_id=TaskRunId.parse(f"TR-{key}"),
        status=TaskRunStatus.SUCCEEDED,
        attempt_ids=(TaskAttemptId.parse(f"TA-{key}"),),
        output=1,
    )


def _result(*outcomes: TaskOutcome) -> WorkflowResult:
    return WorkflowResult(
        run_id=WorkflowRunId.parse("W-result"),
        status=WorkflowRunStatus.SUCCEEDED,
        task_outcomes=outcomes,
        diagnostics=(),
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-result"),
        ),
    )


def test_task_outcome_validation_and_normalization() -> None:
    outcome = _task_outcome()
    assert outcome.attempt_ids == (TaskAttemptId.parse("TA-task"),)

    with pytest.raises(ValueError, match="task_key"):
        TaskOutcome(
            task_key="",
            task_run_id=TaskRunId.parse("TR"),
            status=TaskRunStatus.SUCCEEDED,
        )

    with pytest.raises(TypeError, match="task_run_id"):
        TaskOutcome(
            task_key="a",
            task_run_id="TR",  # type: ignore[arg-type]
            status=TaskRunStatus.SUCCEEDED,
        )

    with pytest.raises(TypeError, match="attempt_ids"):
        TaskOutcome(
            task_key="a",
            task_run_id=TaskRunId.parse("TR"),
            status=TaskRunStatus.SUCCEEDED,
            attempt_ids=("TA",),  # type: ignore[arg-type]
        )


def test_workflow_result_validates_terminal_status_unique_keys_and_diagnostics() -> None:
    with pytest.raises(ValueError, match="terminal"):
        WorkflowResult(
            run_id=WorkflowRunId.parse("W"),
            status=WorkflowRunStatus.RUNNING,
            task_outcomes=(),
            diagnostics=(),
            correlation=CorrelationContext(
                correlation_id=CorrelationId.parse("C"),
            ),
        )

    duplicate = _task_outcome("same")
    with pytest.raises(ValueError, match="unique"):
        _result(duplicate, duplicate)

    with pytest.raises(TypeError, match="diagnostics"):
        WorkflowResult(
            run_id=WorkflowRunId.parse("W"),
            status=WorkflowRunStatus.SUCCEEDED,
            task_outcomes=(),
            diagnostics=(object(),),  # type: ignore[arg-type]
            correlation=CorrelationContext(
                correlation_id=CorrelationId.parse("C"),
            ),
        )


def test_workflow_result_task_lookup_and_diagnostic_projection() -> None:
    diagnostic = Diagnostic(
        code="PWK-RESULT",
        severity=DiagnosticSeverity.INFO,
        summary="result",
    )
    outcome = _task_outcome("a")
    result = WorkflowResult(
        run_id=WorkflowRunId.parse("W"),
        status=WorkflowRunStatus.SUCCEEDED,
        task_outcomes=(outcome,),
        diagnostics=(diagnostic,),
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C"),
        ),
    )

    assert result.task("a") is outcome
    assert result.diagnostics == (diagnostic,)
    with pytest.raises(KeyError):
        result.task("missing")


def test_system_clock_and_uuid_identity_factory_return_canonical_values() -> None:
    now = SystemClock().now()
    assert now.tzinfo is UTC

    factory = UuidRuntimeIdentityFactory()
    run_id = factory.new_workflow_run_id()
    task_run_id = factory.new_task_run_id()
    attempt_id = factory.new_task_attempt_id()
    correlation_id = factory.new_correlation_id()

    assert isinstance(run_id, WorkflowRunId)
    assert isinstance(task_run_id, TaskRunId)
    assert isinstance(attempt_id, TaskAttemptId)
    assert isinstance(correlation_id, CorrelationId)
    assert str(run_id)
    assert str(task_run_id)
    assert str(attempt_id)
    assert str(correlation_id)


def test_system_retry_waiter_validates_delay_and_delegates_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[float] = []
    monkeypatch.setattr(
        "pyworkflowkit.runtime.services.sleep",
        lambda seconds: calls.append(seconds),
    )
    waiter = SystemRetryWaiter()

    waiter.wait(0.0)
    waiter.wait(0.25)

    assert calls == [0.25]

    with pytest.raises(TypeError, match="number"):
        waiter.wait(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="finite"):
        waiter.wait(float("inf"))
    with pytest.raises(ValueError, match="greater than or equal"):
        waiter.wait(-0.1)



@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("status", "confirmed", "status"),
        ("workflow_run_id", "W", "workflow_run_id"),
        ("task_run_id", "TR", "task_run_id"),
        ("attempt_id", "TA", "attempt_id"),
        ("reason", "", "reason"),
    ),
)
def test_cancellation_result_rejects_invalid_boundary_values(
    field: str,
    value: object,
    message: str,
) -> None:
    values: dict[str, object] = {
        "status": CancellationStatus.CONFIRMED,
        "workflow_run_id": WorkflowRunId.parse("W"),
        "task_run_id": TaskRunId.parse("TR"),
        "attempt_id": TaskAttemptId.parse("TA"),
        "reason": "confirmed",
    }
    values[field] = value

    with pytest.raises((TypeError, ValueError), match=message):
        CancellationResult(**values)  # type: ignore[arg-type]
