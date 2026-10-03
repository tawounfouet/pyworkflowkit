"""LOT-14 integration tests for advanced V2 executor routing."""

from __future__ import annotations

import asyncio
import os
import sys

from pyworkflowkit.authoring import RegisteredWorkload, TaskDefinition, WorkflowDefinition
from pyworkflowkit.executors import (
    AsyncExecutor,
    ExecutorRegistry,
    ProcessExecutor,
    SubprocessCommand,
    SubprocessExecutor,
    SubprocessResult,
    TaskExecutionContext,
)
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.planning import WorkflowPlanner
from pyworkflowkit.runtime import WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus


async def _async_transform(context: TaskExecutionContext) -> str:
    await asyncio.sleep(0)
    process_pid = int(context.dependency_outputs["process"])
    return f"pid:{process_pid}"


def test_planner_routes_portable_subprocess_command_without_handler_factory() -> None:
    command = SubprocessCommand(argv=(sys.executable, "-c", "print('ok')"))
    workflow = WorkflowDefinition(
        name="portable-subprocess",
        tasks=(TaskDefinition(key="external", workload=command),),
    )

    plan = WorkflowPlanner().compile(workflow)

    requirement = plan.task("external").executor_requirement
    assert requirement.executor_key == "subprocess"
    assert requirement.workload_kind == "subprocess"
    assert requirement.portable is True


def test_workflow_runtime_routes_process_async_and_subprocess_in_one_dag() -> None:
    process = ProcessExecutor({"jobs.pid": os.getpid}, max_workers=1)
    async_executor = AsyncExecutor(
        {"jobs.async-transform": _async_transform},
        max_concurrency=2,
    )
    subprocess_executor = SubprocessExecutor(max_workers=1)
    registry = ExecutorRegistry((process, async_executor, subprocess_executor))
    runtime = WorkflowRuntime(
        executor_registry=registry,
        metadata=InMemoryMetadataStore(),
    )

    workflow = WorkflowDefinition(
        name="advanced-executors",
        tasks=(
            TaskDefinition(
                key="process",
                workload=RegisteredWorkload(
                    "jobs.pid",
                    executor_key="process",
                ),
            ),
            TaskDefinition(
                key="async",
                workload=RegisteredWorkload(
                    "jobs.async-transform",
                    executor_key="async",
                ),
                dependencies=("process",),
            ),
            TaskDefinition(
                key="subprocess",
                workload=SubprocessCommand(
                    argv=(sys.executable, "-c", "print('external-ok')"),
                ),
                dependencies=("async",),
            ),
        ),
    )

    try:
        result = runtime.run(workflow)
    finally:
        process.shutdown(wait=False)
        async_executor.shutdown(wait=False)
        subprocess_executor.shutdown(wait=False)

    assert result.status is WorkflowRunStatus.SUCCEEDED

    process_pid = result.task("process").output
    assert isinstance(process_pid, int)
    assert process_pid != os.getpid()

    assert result.task("async").output == f"pid:{process_pid}"

    subprocess_output = result.task("subprocess").output
    assert isinstance(subprocess_output, SubprocessResult)
    assert subprocess_output.stdout == "external-ok\n"
    assert subprocess_output.returncode == 0
