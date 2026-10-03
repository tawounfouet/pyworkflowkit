"""LOT-13 WorkflowRuntime integration for per-task executor routing."""

from __future__ import annotations

import threading

from pyworkflowkit.authoring import RegisteredWorkload, TaskDefinition, WorkflowDefinition
from pyworkflowkit.executors import ExecutorRegistry, InlineExecutor, ThreadExecutor
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.planning import WorkflowPlanner
from pyworkflowkit.policies import TimeoutPolicy
from pyworkflowkit.runtime import TaskExecutionContext, WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus


def test_workflow_runtime_routes_each_task_to_its_declared_executor() -> None:
    store = InMemoryMetadataStore()
    thread_names: list[str] = []

    def threaded(context: TaskExecutionContext) -> int:
        thread_names.append(threading.current_thread().name)
        return int(context.dependency_outputs["inline"]) + 1

    thread = ThreadExecutor(
        {"jobs.threaded": threaded},
        max_workers=1,
        thread_name_prefix="pwk-route",
    )
    registry = ExecutorRegistry((InlineExecutor(), thread))
    runtime = WorkflowRuntime(
        executor_registry=registry,
        metadata=store,
    )
    workflow = WorkflowDefinition(
        name="multi-executor",
        tasks=(
            TaskDefinition(key="inline", workload=lambda: 41),
            TaskDefinition(
                key="threaded",
                workload=RegisteredWorkload(
                    "jobs.threaded",
                    executor_key="thread",
                ),
                dependencies=("inline",),
            ),
        ),
    )

    try:
        result = runtime.run(workflow)
    finally:
        thread.shutdown()

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert result.task("inline").output == 41
    assert result.task("threaded").output == 42
    assert len(thread_names) == 1
    assert thread_names[0].startswith("pwk-route")

    plan = WorkflowPlanner().compile(workflow)
    assert plan.task("inline").executor_requirement.executor_key == "inline"
    assert plan.task("threaded").executor_requirement.executor_key == "thread"


def test_legacy_single_executor_constructor_remains_supported() -> None:
    runtime = WorkflowRuntime(
        executor=InlineExecutor(),
        metadata=InMemoryMetadataStore(),
    )

    result = runtime.run(
        WorkflowDefinition(
            name="single-executor",
            tasks=(TaskDefinition(key="task", workload=lambda: "ok"),),
        )
    )

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert runtime.executor_registry.executor_ids == ("inline",)


def test_runtime_can_register_additional_executor_after_construction() -> None:
    thread = ThreadExecutor({"jobs.threaded": lambda: "thread"}, max_workers=1)
    runtime = WorkflowRuntime(
        executor=InlineExecutor(),
        metadata=InMemoryMetadataStore(),
    )
    runtime.register_executor(thread)

    try:
        result = runtime.run(
            WorkflowDefinition(
                name="late-registration",
                tasks=(
                    TaskDefinition(
                        key="threaded",
                        workload=RegisteredWorkload(
                            "jobs.threaded",
                            executor_key="thread",
                        ),
                    ),
                ),
            )
        )
    finally:
        thread.shutdown()

    assert result.status is WorkflowRunStatus.SUCCEEDED
    assert result.task("threaded").output == "thread"


def test_thread_timeout_becomes_unknown_outcome_without_second_attempt() -> None:
    release = threading.Event()

    def slow() -> str:
        release.wait(timeout=2)
        return "late"

    thread = ThreadExecutor({"jobs.slow": slow}, max_workers=1)
    store = InMemoryMetadataStore()
    runtime = WorkflowRuntime(
        executor_registry=ExecutorRegistry((thread,)),
        metadata=store,
    )

    workflow = WorkflowDefinition(
        name="soft-timeout",
        tasks=(
            TaskDefinition(
                key="slow",
                workload=RegisteredWorkload(
                    "jobs.slow",
                    executor_key="thread",
                ),
                timeout_policy=TimeoutPolicy(execution_timeout=0.02),
            ),
        ),
    )

    try:
        result = runtime.run(workflow)
        task_run = store.list_task_runs(result.run_id)[0]
        attempts = store.list_task_attempts(task_run.task_run_id)

        assert result.status is WorkflowRunStatus.UNKNOWN_OUTCOME
        assert len(attempts) == 1
        assert result.failure is not None
        assert result.failure.error_code == "PWK-THREAD-SOFT-TIMEOUT"
    finally:
        release.set()
        thread.shutdown()
