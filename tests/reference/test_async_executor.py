"""M33 reference acceptance for asyncio execution."""

from __future__ import annotations

import asyncio
import threading
import time

from pyworkflowkit.adapters.executors.asyncio import AsyncExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.cancellation import CancellationController
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import (
    TaskRunStatus,
    TimeoutMode,
    WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import TaskId, WorkflowId
from pyworkflowkit.domain.runtime import WorkflowRun


def _runner(
    *,
    executor: AsyncExecutor,
    handlers: HandlerRegistry,
    store: MemoryMetadataStore,
) -> ConcurrentRunner:
    return ConcurrentRunner(
        metadata_store=store,
        handler_registry=handlers,
        executor=executor,
        clock=SystemClock(),
        id_factory=UuidRuntimeIdFactory(),
        sleeper=SystemSleeper(),
        global_limit=executor.capabilities.max_concurrency,
    )


def test_async_executor_runs_fan_out_concurrently() -> None:
    active = 0
    maximum = 0

    async def sibling() -> str:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.05)
        active -= 1
        return "ok"

    handlers = HandlerRegistry()
    handlers.register("handlers:a", sibling)
    handlers.register("handlers:b", sibling)
    store = MemoryMetadataStore()
    executor = AsyncExecutor(max_concurrency=2)
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.async.fanout"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("a"),
                handler_ref="handlers:a",
                executor_key="async",
            ),
            TaskDefinition(
                task_id=TaskId("b"),
                handler_ref="handlers:b",
                executor_key="async",
            ),
        ),
    )

    try:
        run = _runner(executor=executor, handlers=handlers, store=store).run(workflow)

        assert run.status is WorkflowRunStatus.SUCCEEDED
        assert maximum == 2
        assert all(
            task_run.status is TaskRunStatus.SUCCEEDED
            for task_run in store.list_task_runs(run.run_id)
        )
    finally:
        executor.shutdown(wait=False)
        executor.shutdown(wait=True)


def test_async_executor_soft_timeout_uses_existing_failure_contract() -> None:
    async def slow() -> str:
        await asyncio.sleep(0.15)
        return "late"

    handlers = HandlerRegistry()
    handlers.register("handlers:slow", slow)
    store = MemoryMetadataStore()
    executor = AsyncExecutor(max_concurrency=1)
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.async.soft-timeout"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("slow"),
                handler_ref="handlers:slow",
                executor_key="async",
                timeout_seconds=0.02,
                timeout_mode=TimeoutMode.SOFT,
            ),
        ),
    )

    try:
        run = _runner(executor=executor, handlers=handlers, store=store).run(workflow)
        task_run = store.list_task_runs(run.run_id)[0]
        attempt = store.list_task_attempts(task_run.task_run_id)[0]

        assert run.status is WorkflowRunStatus.FAILED
        assert attempt.error_type == "ExecutionTimeoutError"
        assert attempt.error_category == "timeout"
    finally:
        executor.shutdown(wait=False)
        executor.shutdown(wait=True)


def test_cooperative_workflow_cancellation_calls_async_task_cancel() -> None:
    started = threading.Event()

    async def slow() -> str:
        started.set()
        await asyncio.sleep(10)
        return "late"

    handlers = HandlerRegistry()
    handlers.register("handlers:cancel", slow)
    store = MemoryMetadataStore()
    executor = AsyncExecutor(max_concurrency=1)
    cancellation = CancellationController()
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.async.cancellation"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("cancel"),
                handler_ref="handlers:cancel",
                executor_key="async",
            ),
        ),
    )
    runner = _runner(executor=executor, handlers=handlers, store=store)
    result: dict[str, WorkflowRun] = {}

    def run_workflow() -> None:
        result["run"] = runner.run(workflow, cancellation=cancellation)

    coordinator = threading.Thread(target=run_workflow)
    started_at = time.monotonic()
    coordinator.start()
    try:
        assert started.wait(timeout=2.0)
        assert cancellation.request(reason="acceptance") is True
        coordinator.join(timeout=3.0)

        assert coordinator.is_alive() is False
        run = result["run"]
        task_run = store.list_task_runs(run.run_id)[0]

        assert run.status is WorkflowRunStatus.CANCELLED
        assert task_run.status is TaskRunStatus.CANCELLED
        assert time.monotonic() - started_at < 3.0
    finally:
        executor.shutdown(wait=False)
        executor.shutdown(wait=True)
