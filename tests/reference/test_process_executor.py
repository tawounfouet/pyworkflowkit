"""M32 reference acceptance for process-isolated execution."""

from __future__ import annotations

import os
import time
from threading import Thread

from pyworkflowkit.adapters.executors.process import ProcessExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.cancellation import CancellationController
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import TaskRunStatus, TimeoutMode, WorkflowRunStatus
from pyworkflowkit.domain.ids import TaskId, WorkflowId


def _process_pid() -> int:
    return os.getpid()


def _slow_process() -> str:
    time.sleep(5)
    return "late"


def _runner(
    *,
    executor: ProcessExecutor,
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


def test_process_executor_completes_reference_workflow() -> None:
    handlers = HandlerRegistry()
    handlers.register("handlers:a", _process_pid)
    handlers.register("handlers:b", _process_pid)
    store = MemoryMetadataStore()
    executor = ProcessExecutor(max_workers=2)
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.process.success"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("a"),
                handler_ref="handlers:a",
                executor_key="process",
            ),
            TaskDefinition(
                task_id=TaskId("b"),
                handler_ref="handlers:b",
                executor_key="process",
                depends_on=(TaskId("a"),),
            ),
        ),
    )

    try:
        run = _runner(executor=executor, handlers=handlers, store=store).run(workflow)

        assert run.status is WorkflowRunStatus.SUCCEEDED
        assert all(
            task_run.finished_at is not None
            for task_run in store.list_task_runs(run.run_id)
        )
        assert executor.active_handles() == ()
    finally:
        executor.shutdown(wait=False)


def test_hard_timeout_terminates_process_and_fails_run() -> None:
    handlers = HandlerRegistry()
    handlers.register("handlers:slow", _slow_process)
    store = MemoryMetadataStore()
    executor = ProcessExecutor(max_workers=1)
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.process.hard-timeout"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("slow"),
                handler_ref="handlers:slow",
                executor_key="process",
                timeout_seconds=0.1,
                timeout_mode=TimeoutMode.HARD,
            ),
        ),
    )

    started = time.monotonic()
    try:
        run = _runner(executor=executor, handlers=handlers, store=store).run(workflow)

        assert run.status is WorkflowRunStatus.FAILED
        assert time.monotonic() - started < 3.0
        assert executor.active_handles() == ()
    finally:
        executor.shutdown(wait=False)


def test_hard_cancellation_terminates_active_process() -> None:
    handlers = HandlerRegistry()
    handlers.register("handlers:cancel", _slow_process)
    store = MemoryMetadataStore()
    executor = ProcessExecutor(max_workers=1)
    cancellation = CancellationController()
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.process.hard-cancellation"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("cancel"),
                handler_ref="handlers:cancel",
                executor_key="process",
            ),
        ),
    )
    runner = _runner(executor=executor, handlers=handlers, store=store)
    result: dict[str, object] = {}

    def run_workflow() -> None:
        result["run"] = runner.run(workflow, cancellation=cancellation)

    coordinator = Thread(target=run_workflow)
    started = time.monotonic()
    coordinator.start()
    try:
        deadline = time.monotonic() + 3.0
        while not executor.active_handles() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert executor.active_handles()

        assert cancellation.request(reason="acceptance") is True
        coordinator.join(timeout=3.0)

        assert coordinator.is_alive() is False
        run = result["run"]
        assert getattr(run, "status") is WorkflowRunStatus.CANCELLED
        task_runs = store.list_task_runs(getattr(run, "run_id"))
        assert len(task_runs) == 1
        assert task_runs[0].status is TaskRunStatus.CANCELLED
        assert time.monotonic() - started < 4.0
    finally:
        executor.shutdown(wait=False)
