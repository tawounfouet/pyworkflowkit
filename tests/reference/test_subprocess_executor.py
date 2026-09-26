"""M34 reference acceptance for external subprocess execution."""

from __future__ import annotations

import sys
import threading
import time

from pyworkflowkit.adapters.executors.subprocess import SubprocessCommand, SubprocessExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.cancellation import CancellationController
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import TaskRunStatus, TimeoutMode, WorkflowRunStatus
from pyworkflowkit.domain.ids import TaskId, WorkflowId
from pyworkflowkit.domain.runtime import WorkflowRun


def _runner(
    *,
    executor: SubprocessExecutor,
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


def _success_command() -> SubprocessCommand:
    return SubprocessCommand(
        argv=(sys.executable, "-c", "print('external-ok')"),
    )


def _slow_command() -> SubprocessCommand:
    return SubprocessCommand(
        argv=(sys.executable, "-c", "import time; time.sleep(10)"),
    )


def test_subprocess_executor_completes_reference_workflow() -> None:
    handlers = HandlerRegistry()
    handlers.register("handlers:external", _success_command)
    store = MemoryMetadataStore()
    executor = SubprocessExecutor(max_workers=1)
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.subprocess.success"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("external"),
                handler_ref="handlers:external",
                executor_key="subprocess",
            ),
        ),
    )

    try:
        run = _runner(executor=executor, handlers=handlers, store=store).run(workflow)

        assert run.status is WorkflowRunStatus.SUCCEEDED
        assert store.list_task_runs(run.run_id)[0].status is TaskRunStatus.SUCCEEDED
        assert executor.active_handles() == ()
    finally:
        executor.shutdown(wait=False)


def test_hard_timeout_terminates_external_subprocess() -> None:
    handlers = HandlerRegistry()
    handlers.register("handlers:slow", _slow_command)
    store = MemoryMetadataStore()
    executor = SubprocessExecutor(max_workers=1)
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.subprocess.hard-timeout"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("slow"),
                handler_ref="handlers:slow",
                executor_key="subprocess",
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


def test_workflow_cancellation_terminates_external_subprocess() -> None:
    handlers = HandlerRegistry()
    handlers.register("handlers:cancel", _slow_command)
    store = MemoryMetadataStore()
    executor = SubprocessExecutor(max_workers=1)
    cancellation = CancellationController()
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.subprocess.cancellation"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("cancel"),
                handler_ref="handlers:cancel",
                executor_key="subprocess",
            ),
        ),
    )
    runner = _runner(executor=executor, handlers=handlers, store=store)
    result: dict[str, WorkflowRun] = {}

    def run_workflow() -> None:
        result["run"] = runner.run(workflow, cancellation=cancellation)

    coordinator = threading.Thread(target=run_workflow)
    started = time.monotonic()
    coordinator.start()
    try:
        deadline = time.monotonic() + 2.0
        while not executor.active_handles() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert executor.active_handles()

        assert cancellation.request(reason="acceptance") is True
        coordinator.join(timeout=3.0)

        assert coordinator.is_alive() is False
        run = result["run"]
        task_run = store.list_task_runs(run.run_id)[0]
        assert run.status is WorkflowRunStatus.CANCELLED
        assert task_run.status is TaskRunStatus.CANCELLED
        assert time.monotonic() - started < 3.0
    finally:
        executor.shutdown(wait=False)
