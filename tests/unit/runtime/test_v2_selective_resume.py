"""Unit tests for LOT-33 V2 selective resume and checkpoint recovery."""

from __future__ import annotations

import pytest

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.errors import (
    GraphTopologyMismatchError,
    InvalidRunStateForResumeError,
    WorkflowNotFoundError,
)
from pyworkflowkit.executors import InlineExecutor, TaskExecutionContext
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.runtime import (
    RuntimeEventType,
    WorkflowRunId,
    WorkflowRuntime,
)
from pyworkflowkit.states import TaskRunStatus, WorkflowRunStatus


def test_resume_run_raises_when_original_run_not_found() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
    workflow = WorkflowDefinition(
        name="test-workflow",
        tasks=(TaskDefinition(key="task-a", workload=lambda: 1),),
    )

    with pytest.raises(WorkflowNotFoundError) as exc_info:
        runtime.resume_run("non-existent-run-id", workflow)

    assert "non-existent-run-id" in str(exc_info.value)


def test_resume_run_raises_on_invalid_run_id_type() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
    workflow = WorkflowDefinition(
        name="test-workflow",
        tasks=(TaskDefinition(key="task-a", workload=lambda: 1),),
    )

    with pytest.raises(TypeError, match="original_run_id must be a WorkflowRunId or str"):
        runtime.resume_run(12345, workflow)  # type: ignore[arg-type]


def test_resume_run_raises_when_original_run_is_running() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
    workflow = WorkflowDefinition(
        name="test-workflow",
        tasks=(TaskDefinition(key="task-a", workload=lambda: 1),),
    )

    # Simulate an active run in RUNNING status
    run_id = WorkflowRunId.parse("active-run-1")
    from datetime import UTC, datetime

    from pyworkflowkit.runtime import CorrelationContext, WorkflowRun

    run = WorkflowRun(
        run_id=run_id,
        workflow_name="test-workflow",
        workflow_version="1",
        definition_fingerprint=workflow.fingerprint(),
        plan_fingerprint="sha256:plan",
        correlation=CorrelationContext(),
        created_at=datetime.now(UTC),
    )
    store.create_workflow_run(run)
    store.update_workflow_run(
        run,
        expected_status=WorkflowRunStatus.PENDING,
        transitioned_at=datetime.now(UTC),
    )
    # transition to RUNNING
    from pyworkflowkit.states import WorkflowRunStateMachine

    WorkflowRunStateMachine().transition(run, WorkflowRunStatus.RUNNING, at=datetime.now(UTC))
    store.update_workflow_run(
        run,
        expected_status=WorkflowRunStatus.PENDING,
        transitioned_at=datetime.now(UTC),
    )

    with pytest.raises(InvalidRunStateForResumeError) as exc_info:
        runtime.resume_run(run_id, workflow)

    assert "RUNNING" in str(exc_info.value)


def test_resume_run_raises_on_topology_fingerprint_mismatch() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)

    workflow_v2 = WorkflowDefinition(
        name="test-workflow",
        tasks=(
            TaskDefinition(key="task-a", workload=lambda: 1),
            TaskDefinition(key="task-b", workload=lambda: 2),
        ),
    )

    # Fail v1 run
    failing_workflow_v1 = WorkflowDefinition(
        name="test-workflow",
        tasks=(
            TaskDefinition(
                key="task-a",
                workload=lambda: (_ for _ in ()).throw(RuntimeError("fail")),
            ),
        ),
    )
    result_v1 = runtime.run(failing_workflow_v1)
    assert result_v1.status is WorkflowRunStatus.FAILED

    with pytest.raises(GraphTopologyMismatchError) as exc_info:
        runtime.resume_run(result_v1.run_id, workflow_v2)

    assert "graph topology mismatch" in str(exc_info.value)


def test_selective_resume_skips_successful_tasks_and_reuses_checkpoints() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)

    call_counts: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}
    c_should_fail = True

    from collections.abc import Mapping

    def workload_a() -> dict[str, int]:
        call_counts["a"] += 1
        return {"value_a": 10}

    def workload_b(context: TaskExecutionContext) -> dict[str, int]:
        call_counts["b"] += 1
        dep = context.dependency_outputs["task-a"]
        assert isinstance(dep, (dict, Mapping))
        return {"value_b": int(dep["value_a"]) + 20}

    def workload_c(context: TaskExecutionContext) -> dict[str, int]:
        call_counts["c"] += 1
        if c_should_fail:
            raise ValueError("simulated crash at task C")
        dep = context.dependency_outputs["task-b"]
        assert isinstance(dep, (dict, Mapping))
        return {"value_c": int(dep["value_b"]) + 30}

    def workload_d(context: TaskExecutionContext) -> dict[str, int]:
        call_counts["d"] += 1
        dep = context.dependency_outputs["task-c"]
        assert isinstance(dep, (dict, Mapping))
        return {"value_d": int(dep["value_c"]) + 40}

    workflow = WorkflowDefinition(
        name="resume-pipeline",
        tasks=(
            TaskDefinition(key="task-a", workload=workload_a),
            TaskDefinition(key="task-b", workload=workload_b, dependencies=("task-a",)),
            TaskDefinition(key="task-c", workload=workload_c, dependencies=("task-b",)),
            TaskDefinition(key="task-d", workload=workload_d, dependencies=("task-c",)),
        ),
    )

    # 1. First run fails at task-c
    initial_result = runtime.run(workflow)
    assert initial_result.status is WorkflowRunStatus.FAILED
    assert initial_result.task("task-a").status is TaskRunStatus.SUCCEEDED
    assert initial_result.task("task-b").status is TaskRunStatus.SUCCEEDED
    assert initial_result.task("task-c").status is TaskRunStatus.FAILED
    assert initial_result.task("task-d").status is TaskRunStatus.SKIPPED
    assert call_counts == {"a": 1, "b": 1, "c": 1, "d": 0}

    # 2. Fix task-c and resume
    c_should_fail = False
    resumed_result = runtime.resume_run(initial_result.run_id, workflow)
    assert resumed_result.status is WorkflowRunStatus.SUCCEEDED

    # Check lineage / parent link
    persisted_resumed_run = store.get_workflow_run(resumed_result.run_id)
    assert persisted_resumed_run.resume_of_run_id == str(initial_result.run_id)

    # Workloads for task-a and task-b should NOT have been called again!
    assert call_counts == {"a": 1, "b": 1, "c": 2, "d": 1}

    # Verify task statuses
    task_a = resumed_result.task("task-a")
    task_b = resumed_result.task("task-b")
    task_c = resumed_result.task("task-c")
    task_d = resumed_result.task("task-d")

    assert task_a.status is TaskRunStatus.REUSED
    assert task_a.output == {"value_a": 10}
    assert task_a.attempt_ids == ()

    assert task_b.status is TaskRunStatus.REUSED
    assert task_b.output == {"value_b": 30}
    assert task_b.attempt_ids == ()

    assert task_c.status is TaskRunStatus.SUCCEEDED
    assert task_c.output == {"value_c": 60}
    assert len(task_c.attempt_ids) == 1

    assert task_d.status is TaskRunStatus.SUCCEEDED
    assert task_d.output == {"value_d": 100}
    assert len(task_d.attempt_ids) == 1

    # Verify events
    events = runtime.events(resumed_result.run_id)
    event_types = tuple(e.event_type for e in events)
    assert RuntimeEventType.WORKFLOW_RESUMED in event_types
    assert RuntimeEventType.TASK_RESUMED in event_types

    # Verify diagnostics include task reused evidence
    reused_diagnostics = [d for d in resumed_result.diagnostics if d.code == "PWK-TASK-REUSED"]
    assert len(reused_diagnostics) == 2
    reused_keys = {dict(d.details)["task_key"] for d in reused_diagnostics}
    assert reused_keys == {"task-a", "task-b"}


def test_selective_resume_recomputes_volatile_tasks() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)

    call_counts: dict[str, int] = {"a": 0, "b": 0, "c": 0}
    c_should_fail = True

    def workload_a() -> str:
        call_counts["a"] += 1
        return "a-done"

    def workload_volatile() -> str:
        call_counts["b"] += 1
        return f"b-token-{call_counts['b']}"

    def workload_c() -> str:
        call_counts["c"] += 1
        if c_should_fail:
            raise RuntimeError("c-fail")
        return "c-done"

    wf = WorkflowDefinition(
        name="volatile-pipeline",
        tasks=(
            TaskDefinition(key="task-a", workload=workload_a),
            TaskDefinition(
                key="task-b",
                workload=workload_volatile,
                dependencies=("task-a",),
                is_deterministic=False,  # Volatile!
            ),
            TaskDefinition(key="task-c", workload=workload_c, dependencies=("task-b",)),
        ),
    )

    r1 = runtime.run(wf)
    assert r1.status is WorkflowRunStatus.FAILED
    assert call_counts == {"a": 1, "b": 1, "c": 1}

    c_should_fail = False
    r2 = runtime.resume_run(r1.run_id, wf)
    assert r2.status is WorkflowRunStatus.SUCCEEDED

    # task-a is deterministic -> REUSED (not re-executed)
    assert call_counts["a"] == 1
    assert r2.task("task-a").status is TaskRunStatus.REUSED

    # task-b is volatile -> RE-EXECUTED!
    assert call_counts["b"] == 2
    assert r2.task("task-b").status is TaskRunStatus.SUCCEEDED
    assert r2.task("task-b").output == "b-token-2"

    # task-c was downstream of volatile task-b -> RE-EXECUTED!
    assert call_counts["c"] == 2
    assert r2.task("task-c").status is TaskRunStatus.SUCCEEDED


def test_selective_resume_force_recompute_tasks() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)

    call_counts: dict[str, int] = {"a": 0, "b": 0, "c": 0}
    c_should_fail = True

    def workload_a() -> str:
        call_counts["a"] += 1
        return "a"

    def workload_b() -> str:
        call_counts["b"] += 1
        return "b"

    def workload_c() -> str:
        call_counts["c"] += 1
        if c_should_fail:
            raise RuntimeError("c")
        return "c"

    wf = WorkflowDefinition(
        name="force-pipeline",
        tasks=(
            TaskDefinition(key="task-a", workload=workload_a),
            TaskDefinition(key="task-b", workload=workload_b, dependencies=("task-a",)),
            TaskDefinition(key="task-c", workload=workload_c, dependencies=("task-b",)),
        ),
    )
    r1 = runtime.run(wf)
    assert r1.status is WorkflowRunStatus.FAILED
    assert call_counts == {"a": 1, "b": 1, "c": 1}

    c_should_fail = False
    # Force recompute task-a
    r2 = runtime.resume_run(r1.run_id, wf, force_recompute_tasks=["task-a"])
    assert r2.status is WorkflowRunStatus.SUCCEEDED

    # Because task-a was forced, task-b and task-c downstream must also recompute!
    assert call_counts == {"a": 2, "b": 2, "c": 2}
    assert r2.task("task-a").status is TaskRunStatus.SUCCEEDED
    assert r2.task("task-b").status is TaskRunStatus.SUCCEEDED
    assert r2.task("task-c").status is TaskRunStatus.SUCCEEDED


def test_selective_resume_diamond_graph() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)

    call_counts: dict[str, int] = {"a": 0, "b": 0, "c": 0, "d": 0}
    c_should_fail = True

    def workload_a() -> int:
        call_counts["a"] += 1
        return 1

    def workload_b() -> int:
        call_counts["b"] += 1
        return 2

    def workload_c() -> int:
        call_counts["c"] += 1
        if c_should_fail:
            raise RuntimeError("fail")
        return 3

    def workload_d(context: TaskExecutionContext) -> int:
        call_counts["d"] += 1
        b_val = context.dependency_outputs["task-b"]
        c_val = context.dependency_outputs["task-c"]
        assert isinstance(b_val, int) and isinstance(c_val, int)
        return b_val + c_val

    # Diamond: a -> b, a -> c, [b, c] -> d
    wf = WorkflowDefinition(
        name="diamond-pipeline",
        tasks=(
            TaskDefinition(key="task-a", workload=workload_a),
            TaskDefinition(key="task-b", workload=workload_b, dependencies=("task-a",)),
            TaskDefinition(key="task-c", workload=workload_c, dependencies=("task-a",)),
            TaskDefinition(
                key="task-d",
                workload=workload_d,
                dependencies=("task-b", "task-c"),
            ),
        ),
    )
    r1 = runtime.run(wf)
    assert r1.status is WorkflowRunStatus.FAILED
    assert r1.task("task-a").status is TaskRunStatus.SUCCEEDED
    assert r1.task("task-b").status is TaskRunStatus.SUCCEEDED
    assert r1.task("task-c").status is TaskRunStatus.FAILED
    assert r1.task("task-d").status is TaskRunStatus.SKIPPED
    assert call_counts == {"a": 1, "b": 1, "c": 1, "d": 0}

    c_should_fail = False
    r2 = runtime.resume_run(r1.run_id, wf)
    assert r2.status is WorkflowRunStatus.SUCCEEDED

    # a and b were reused!
    assert r2.task("task-a").status is TaskRunStatus.REUSED
    assert r2.task("task-b").status is TaskRunStatus.REUSED
    # c and d were executed!
    assert r2.task("task-c").status is TaskRunStatus.SUCCEEDED
    assert r2.task("task-d").status is TaskRunStatus.SUCCEEDED
    assert r2.task("task-d").output == 5
    assert call_counts == {"a": 1, "b": 1, "c": 2, "d": 1}


def test_chain_of_multiple_resumes() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)

    call_counts: dict[str, int] = {"a": 0, "b": 0, "c": 0}
    b_fails = True
    c_fails = True

    def workload_a() -> str:
        call_counts["a"] += 1
        return "A"

    def workload_b() -> str:
        call_counts["b"] += 1
        if b_fails:
            raise RuntimeError("B fail")
        return "B"

    def workload_c() -> str:
        call_counts["c"] += 1
        if c_fails:
            raise RuntimeError("C fail")
        return "C"

    wf = WorkflowDefinition(
        name="multi-resume",
        tasks=(
            TaskDefinition(key="task-a", workload=workload_a),
            TaskDefinition(key="task-b", workload=workload_b, dependencies=("task-a",)),
            TaskDefinition(key="task-c", workload=workload_c, dependencies=("task-b",)),
        ),
    )

    # Run 1: fails at B
    r1 = runtime.run(wf)
    assert r1.status is WorkflowRunStatus.FAILED
    assert call_counts == {"a": 1, "b": 1, "c": 0}

    # Run 2: resume of Run 1, B fixed, but C fails
    b_fails = False
    r2 = runtime.resume_run(r1.run_id, wf)
    assert r2.status is WorkflowRunStatus.FAILED
    assert r2.task("task-a").status is TaskRunStatus.REUSED
    assert r2.task("task-b").status is TaskRunStatus.SUCCEEDED
    assert r2.task("task-c").status is TaskRunStatus.FAILED
    assert call_counts == {"a": 1, "b": 2, "c": 1}

    # Run 3: resume of Run 2, C fixed
    c_fails = False
    r3 = runtime.resume_run(r2.run_id, wf)
    assert r3.status is WorkflowRunStatus.SUCCEEDED
    # task-a and task-b should be reused from Run 2!
    assert r3.task("task-a").status is TaskRunStatus.REUSED
    assert r3.task("task-b").status is TaskRunStatus.REUSED
    assert r3.task("task-c").status is TaskRunStatus.SUCCEEDED
    assert call_counts == {"a": 1, "b": 2, "c": 2}

    # Lineage links
    w1 = store.get_workflow_run(r1.run_id)
    w2 = store.get_workflow_run(r2.run_id)
    w3 = store.get_workflow_run(r3.run_id)
    assert w1.resume_of_run_id is None
    assert w2.resume_of_run_id == str(r1.run_id)
    assert w3.resume_of_run_id == str(r2.run_id)


def test_resume_run_with_custom_correlation_and_execution_plan() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)

    c_fails = True

    def workload_a() -> str:
        return "a"

    def workload_b() -> str:
        if c_fails:
            raise RuntimeError("fail b")
        return "b"

    wf = WorkflowDefinition(
        name="custom-corr",
        tasks=(
            TaskDefinition(key="task-a", workload=workload_a),
            TaskDefinition(key="task-b", workload=workload_b, dependencies=("task-a",)),
        ),
    )
    plan = runtime._planner.compile(wf)
    r1 = runtime.run(plan)
    assert r1.status is WorkflowRunStatus.FAILED

    c_fails = False
    from pyworkflowkit.runtime import CorrelationContext

    custom_corr = CorrelationContext(
        correlation_id=runtime._identity_factory.new_correlation_id(),
        causation_id="cause-999",
        parent_execution_id="parent-999",
    )
    r2 = runtime.resume_run(r1.run_id, plan, correlation=custom_corr)
    assert r2.status is WorkflowRunStatus.SUCCEEDED

    w2 = store.get_workflow_run(r2.run_id)
    assert w2.correlation.causation_id == "cause-999"
    assert w2.correlation.parent_execution_id == "parent-999"


def test_resume_run_on_cancelled_and_timed_out_runs() -> None:
    from datetime import UTC, datetime

    from pyworkflowkit.runtime import CorrelationContext, WorkflowRun
    from pyworkflowkit.states import WorkflowRunStateMachine

    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
    wf = WorkflowDefinition(
        name="resume-terminal-states",
        tasks=(TaskDefinition(key="task-a", workload=lambda: "ok"),),
    )

    now = datetime.now(UTC)
    state_machine = WorkflowRunStateMachine()

    # 1. CANCELLED run
    run_cancelled = WorkflowRun(
        run_id=runtime._identity_factory.new_workflow_run_id(),
        workflow_name=wf.name,
        workflow_version=wf.version,
        definition_fingerprint=wf.fingerprint(),
        plan_fingerprint="sha256:plan",
        correlation=CorrelationContext(),
        created_at=now,
    )
    store.create_workflow_run(run_cancelled)
    state_machine.transition(run_cancelled, WorkflowRunStatus.RUNNING, at=now)
    store.update_workflow_run(
        run_cancelled, expected_status=WorkflowRunStatus.PENDING, transitioned_at=now
    )
    state_machine.transition(run_cancelled, WorkflowRunStatus.CANCELLATION_REQUESTED, at=now)
    store.update_workflow_run(
        run_cancelled, expected_status=WorkflowRunStatus.RUNNING, transitioned_at=now
    )
    state_machine.transition(run_cancelled, WorkflowRunStatus.CANCELLED, at=now)
    store.update_workflow_run(
        run_cancelled,
        expected_status=WorkflowRunStatus.CANCELLATION_REQUESTED,
        transitioned_at=now,
    )

    resumed_c = runtime.resume_run(run_cancelled.run_id, wf)
    assert resumed_c.status is WorkflowRunStatus.SUCCEEDED

    # 2. TIMED_OUT run
    run_timeout = WorkflowRun(
        run_id=runtime._identity_factory.new_workflow_run_id(),
        workflow_name=wf.name,
        workflow_version=wf.version,
        definition_fingerprint=wf.fingerprint(),
        plan_fingerprint="sha256:plan",
        correlation=CorrelationContext(),
        created_at=now,
    )
    store.create_workflow_run(run_timeout)
    state_machine.transition(run_timeout, WorkflowRunStatus.RUNNING, at=now)
    store.update_workflow_run(
        run_timeout, expected_status=WorkflowRunStatus.PENDING, transitioned_at=now
    )
    state_machine.transition(run_timeout, WorkflowRunStatus.TIMED_OUT, at=now)
    store.update_workflow_run(
        run_timeout, expected_status=WorkflowRunStatus.RUNNING, transitioned_at=now
    )

    resumed_t = runtime.resume_run(run_timeout.run_id, wf)
    assert resumed_t.status is WorkflowRunStatus.SUCCEEDED


def test_classify_tasks_missing_parent_or_missing_checkpoint() -> None:
    from datetime import UTC, datetime

    from pyworkflowkit.runtime import TaskRun
    from pyworkflowkit.runtime._resume import classify_tasks_for_resume

    now = datetime.now(UTC)
    store = InMemoryMetadataStore()
    wf = WorkflowDefinition(
        name="missing-tests",
        tasks=(
            TaskDefinition(key="task-a", workload=lambda: 1),
            TaskDefinition(key="task-b", workload=lambda: 2),
        ),
    )
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
    plan = runtime._planner.compile(wf)

    # 1. task-a has SUCCEEDED status, but no checkpoint in store (raises MetadataNotFoundError)
    t_a = TaskRun(
        task_run_id=runtime._identity_factory.new_task_run_id(),
        workflow_run_id=runtime._identity_factory.new_workflow_run_id(),
        task_key="task-a",
        created_at=now,
    )
    t_a._status = TaskRunStatus.SUCCEEDED
    t_a.started_at = now
    t_a.ended_at = now

    # 2. parent_task_run missing for task-b
    parent_runs = {"task-a": t_a}
    classification = classify_tasks_for_resume(
        plan=plan,
        parent_task_runs=parent_runs,
        metadata=store,
    )
    assert classification.reused_keys == frozenset()


def test_task_definition_is_deterministic_validation() -> None:
    with pytest.raises(TypeError, match="is_deterministic must be a bool"):
        TaskDefinition(key="task-a", workload=lambda: 1, is_deterministic="no")  # type: ignore[arg-type]

    t1 = TaskDefinition(key="t", workload=lambda: 1, is_deterministic=True)
    t2 = TaskDefinition(key="t", workload=lambda: 1, is_deterministic=False)
    assert t1.is_deterministic is True
    assert t2.is_deterministic is False
    assert t1.fingerprint_payload() != t2.fingerprint_payload()

    wf = WorkflowDefinition(
        name="sub",
        tasks=(TaskDefinition(key="inner", workload=lambda: 1),),
    )
    sub_task_det = wf.as_task("sub-det", is_deterministic=True)
    sub_task_vol = wf.as_task("sub-vol", is_deterministic=False)
    assert sub_task_det.is_deterministic is True
    assert sub_task_vol.is_deterministic is False


def test_workflow_run_resume_of_run_id_validation() -> None:
    from datetime import UTC, datetime

    from pyworkflowkit.runtime import CorrelationContext, WorkflowRun

    now = datetime.now(UTC)
    with pytest.raises(TypeError, match="resume_of_run_id must be a str"):
        WorkflowRun(
            run_id=WorkflowRunId.parse("w-1"),
            workflow_name="wf",
            workflow_version="1",
            definition_fingerprint="def",
            plan_fingerprint="plan",
            correlation=CorrelationContext(),
            created_at=now,
            resume_of_run_id=12345,  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="resume_of_run_id must not be empty"):
        WorkflowRun(
            run_id=WorkflowRunId.parse("w-1"),
            workflow_name="wf",
            workflow_version="1",
            definition_fingerprint="def",
            plan_fingerprint="plan",
            correlation=CorrelationContext(),
            created_at=now,
            resume_of_run_id="   ",
        )


def test_task_run_state_machine_reused_transitions() -> None:
    from datetime import UTC, datetime

    from pyworkflowkit.errors import InvalidStateTransitionError
    from pyworkflowkit.runtime import TaskRun, TaskRunId
    from pyworkflowkit.states import TaskRunStateMachine

    now = datetime.now(UTC)
    sm = TaskRunStateMachine()
    tr = TaskRun(
        task_run_id=TaskRunId.parse("tr-1"),
        workflow_run_id=WorkflowRunId.parse("w-1"),
        task_key="t-1",
        created_at=now,
    )
    sm.transition(tr, TaskRunStatus.REUSED, at=now)
    assert tr.status is TaskRunStatus.REUSED
    assert tr.started_at == now
    assert tr.ended_at == now

    with pytest.raises(InvalidStateTransitionError):
        sm.transition(tr, TaskRunStatus.RUNNING, at=now)


def test_workflow_runtime_type_guards() -> None:
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
    wf = WorkflowDefinition(
        name="type-guards",
        tasks=(TaskDefinition(key="task-a", workload=lambda: 1),),
    )

    with pytest.raises(TypeError, match="workflow_run_id must be a WorkflowRunId"):
        runtime.events("invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="workflow_run_id must be a WorkflowRunId"):
        runtime.manifest("invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="workflow_run_id must be a WorkflowRunId"):
        runtime.lineage(wf, "invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="workflow_run_id must be a WorkflowRunId"):
        runtime.inspect(wf, "invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="workflow_run_id must be a WorkflowRunId"):
        runtime.recovery_assessment("invalid")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="workflow_run_id must be a WorkflowRunId"):
        runtime.reconcile_run("invalid")  # type: ignore[arg-type]


def test_workflow_runtime_cancellation_and_evaluator_guards() -> None:
    from datetime import UTC, datetime

    from pyworkflowkit.executors import CancellationStatus
    from pyworkflowkit.runtime import (
        CorrelationContext,
        TaskRun,
        WorkflowRun,
    )
    from pyworkflowkit.states import WorkflowRunStateMachine

    store = InMemoryMetadataStore()
    with pytest.raises(TypeError, match="retry_evaluator must be a RetryEvaluator"):
        WorkflowRuntime(executor=InlineExecutor(), metadata=store, retry_evaluator="bad")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="retry_waiter must satisfy RetryWaiter"):
        WorkflowRuntime(executor=InlineExecutor(), metadata=store, retry_waiter="bad")  # type: ignore[arg-type]

    runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
    now = datetime.now(UTC)

    # 1. cancel() on UNKNOWN_OUTCOME workflow
    run = WorkflowRun(
        run_id=runtime._identity_factory.new_workflow_run_id(),
        workflow_name="wf",
        workflow_version="1",
        definition_fingerprint="d",
        plan_fingerprint="p",
        correlation=CorrelationContext(),
        created_at=now,
    )
    store.create_workflow_run(run)
    WorkflowRunStateMachine().transition(run, WorkflowRunStatus.RUNNING, at=now)
    store.update_workflow_run(run, expected_status=WorkflowRunStatus.PENDING, transitioned_at=now)
    WorkflowRunStateMachine().transition(run, WorkflowRunStatus.UNKNOWN_OUTCOME, at=now)
    store.update_workflow_run(run, expected_status=WorkflowRunStatus.RUNNING, transitioned_at=now)

    res_unknown = runtime.cancel(run.run_id)
    assert res_unknown.status is CancellationStatus.UNCONFIRMED

    # 2. cancel_task guards
    with pytest.raises(TypeError, match="task_run_id must be a TaskRunId"):
        runtime.cancel_task("not-a-task-run-id")

    t_run = TaskRun(
        task_run_id=runtime._identity_factory.new_task_run_id(),
        workflow_run_id=run.run_id,
        task_key="t1",
        created_at=now,
    )
    store.create_task_run(t_run)

    # PENDING -> cancel_task cancels it
    t_res = runtime.cancel_task(t_run.task_run_id)
    assert t_res.status is CancellationStatus.CONFIRMED

    # Already CANCELLED (terminal) -> ALREADY_TERMINAL
    t_res_term = runtime.cancel_task(t_run.task_run_id)
    assert t_res_term.status is CancellationStatus.ALREADY_TERMINAL

    # 3. RUNNING task with attempt
    from pyworkflowkit.runtime import TaskAttempt
    from pyworkflowkit.states import TaskAttemptStateMachine, TaskAttemptStatus

    t_run2 = TaskRun(
        task_run_id=runtime._identity_factory.new_task_run_id(),
        workflow_run_id=run.run_id,
        task_key="t2",
        created_at=now,
    )
    store.create_task_run(t_run2)
    runtime._task_states.transition(t_run2, TaskRunStatus.READY, at=now)
    store.update_task_run(t_run2, expected_status=TaskRunStatus.PENDING, transitioned_at=now)
    runtime._task_states.transition(t_run2, TaskRunStatus.RUNNING, at=now)
    store.update_task_run(t_run2, expected_status=TaskRunStatus.READY, transitioned_at=now)

    attempt = TaskAttempt(
        attempt_id=runtime._identity_factory.new_task_attempt_id(),
        task_run_id=t_run2.task_run_id,
        attempt_number=1,
        created_at=now,
    )
    store.append_task_attempt(attempt)
    TaskAttemptStateMachine().transition(attempt, TaskAttemptStatus.STARTING, at=now)
    store.update_task_attempt(
        attempt, expected_status=TaskAttemptStatus.PENDING, transitioned_at=now
    )
    TaskAttemptStateMachine().transition(attempt, TaskAttemptStatus.RUNNING, at=now)
    store.update_task_attempt(
        attempt, expected_status=TaskAttemptStatus.STARTING, transitioned_at=now
    )

    # When no active request is remembered -> active_execution_handle_not_available (UNCONFIRMED)
    t_res_running = runtime.cancel_task(t_run2.task_run_id)
    assert t_res_running.status is CancellationStatus.UNCONFIRMED
    assert t_res_running.reason == "active_execution_handle_not_available"

    # 4. Task in UNKNOWN_OUTCOME -> cancel_task returns UNCONFIRMED
    t_run3 = TaskRun(
        task_run_id=runtime._identity_factory.new_task_run_id(),
        workflow_run_id=run.run_id,
        task_key="t3",
        created_at=now,
    )
    store.create_task_run(t_run3)
    runtime._task_states.transition(t_run3, TaskRunStatus.READY, at=now)
    store.update_task_run(t_run3, expected_status=TaskRunStatus.PENDING, transitioned_at=now)
    runtime._task_states.transition(t_run3, TaskRunStatus.RUNNING, at=now)
    store.update_task_run(t_run3, expected_status=TaskRunStatus.READY, transitioned_at=now)
    runtime._task_states.transition(t_run3, TaskRunStatus.UNKNOWN_OUTCOME, at=now)
    store.update_task_run(t_run3, expected_status=TaskRunStatus.RUNNING, transitioned_at=now)
    t_res_unk = runtime.cancel_task(t_run3.task_run_id)
    assert t_res_unk.status is CancellationStatus.UNCONFIRMED
    assert t_res_unk.reason == "task_outcome_already_unknown"

    # 5. Task in RUNNING with terminal attempt -> cancel_task returns ALREADY_TERMINAL
    t_run4 = TaskRun(
        task_run_id=runtime._identity_factory.new_task_run_id(),
        workflow_run_id=run.run_id,
        task_key="t4",
        created_at=now,
    )
    store.create_task_run(t_run4)
    runtime._task_states.transition(t_run4, TaskRunStatus.READY, at=now)
    store.update_task_run(t_run4, expected_status=TaskRunStatus.PENDING, transitioned_at=now)
    runtime._task_states.transition(t_run4, TaskRunStatus.RUNNING, at=now)
    store.update_task_run(t_run4, expected_status=TaskRunStatus.READY, transitioned_at=now)

    attempt_term = TaskAttempt(
        attempt_id=runtime._identity_factory.new_task_attempt_id(),
        task_run_id=t_run4.task_run_id,
        attempt_number=1,
        created_at=now,
    )
    store.append_task_attempt(attempt_term)
    TaskAttemptStateMachine().transition(attempt_term, TaskAttemptStatus.STARTING, at=now)
    store.update_task_attempt(
        attempt_term, expected_status=TaskAttemptStatus.PENDING, transitioned_at=now
    )
    TaskAttemptStateMachine().transition(attempt_term, TaskAttemptStatus.RUNNING, at=now)
    store.update_task_attempt(
        attempt_term, expected_status=TaskAttemptStatus.STARTING, transitioned_at=now
    )
    TaskAttemptStateMachine().transition(attempt_term, TaskAttemptStatus.SUCCEEDED, at=now)
    store.update_task_attempt(
        attempt_term, expected_status=TaskAttemptStatus.RUNNING, transitioned_at=now
    )
    t_res_term_att = runtime.cancel_task(t_run4.task_run_id)
    assert t_res_term_att.status is CancellationStatus.ALREADY_TERMINAL

    # 6. Recovery assessment and candidate discovery
    cands = runtime.recovery_candidates()
    assert isinstance(cands, tuple)
    assess = runtime.recovery_assessment(run.run_id)
    assert assess is not None
    recon = runtime.reconcile_run(run.run_id)
    assert recon is not None

    # 7. RUNNING task with no attempt -> cancel_task returns UNCONFIRMED
    t_run5 = TaskRun(
        task_run_id=runtime._identity_factory.new_task_run_id(),
        workflow_run_id=run.run_id,
        task_key="t5",
        created_at=now,
    )
    store.create_task_run(t_run5)
    runtime._task_states.transition(t_run5, TaskRunStatus.READY, at=now)
    store.update_task_run(t_run5, expected_status=TaskRunStatus.PENDING, transitioned_at=now)
    runtime._task_states.transition(t_run5, TaskRunStatus.RUNNING, at=now)
    store.update_task_run(t_run5, expected_status=TaskRunStatus.READY, transitioned_at=now)
    t_res_no_att = runtime.cancel_task(t_run5.task_run_id)
    assert t_res_no_att.status is CancellationStatus.UNCONFIRMED
    assert t_res_no_att.reason == "running_task_has_no_persisted_attempt"

    # 8. Cancel RUNNING workflow with PENDING task -> transitions to CANCELLED
    run_act = WorkflowRun(
        run_id=runtime._identity_factory.new_workflow_run_id(),
        workflow_name="wf_act",
        workflow_version="1",
        definition_fingerprint="d",
        plan_fingerprint="p",
        correlation=CorrelationContext(),
        created_at=now,
    )
    store.create_workflow_run(run_act)
    WorkflowRunStateMachine().transition(run_act, WorkflowRunStatus.RUNNING, at=now)
    store.update_workflow_run(
        run_act, expected_status=WorkflowRunStatus.PENDING, transitioned_at=now
    )

    t_pend = TaskRun(
        task_run_id=runtime._identity_factory.new_task_run_id(),
        workflow_run_id=run_act.run_id,
        task_key="t_pend",
        created_at=now,
    )
    store.create_task_run(t_pend)

    res_wf_cancel = runtime.cancel(run_act.run_id)
    assert res_wf_cancel.status is CancellationStatus.CONFIRMED

    # 9. Register verifier and executor
    from pyworkflowkit.runtime import ExternalRunRef, ExternalRunStatus

    class DummyVerifier:
        provider = "dummy_provider"

        def verify(self, ref: ExternalRunRef) -> ExternalRunStatus:
            return ExternalRunStatus.SUCCEEDED

    runtime.register_external_run_verifier(DummyVerifier())

    from pyworkflowkit.executors import ExecutorDescriptor

    class CustomExecutor(InlineExecutor):
        @property
        def descriptor(self) -> ExecutorDescriptor:
            return ExecutorDescriptor(
                executor_id="custom_exec",
                display_name="Custom",
                executor_version="1.0",
            )

    runtime.register_executor(CustomExecutor())
    assert runtime.executor_registry is not None
