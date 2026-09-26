"""M31 timeout reference acceptance coverage."""

import threading

from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import TaskAttemptStatus, TaskRunStatus, TimeoutMode, WorkflowRunStatus
from pyworkflowkit.domain.ids import TaskId, WorkflowId


def test_soft_timeout_becomes_failed_attempt_and_failed_workflow() -> None:
    registry = HandlerRegistry()

    def slow() -> str:
        threading.Event().wait(0.05)
        return "late"

    registry.register("handlers:slow", slow)
    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.timeout"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("slow"),
                handler_ref="handlers:slow",
                executor_key="thread",
                timeout_seconds=0.01,
                timeout_mode=TimeoutMode.SOFT,
            ),
        ),
    )

    store = MemoryMetadataStore()
    executor = ThreadExecutor(max_workers=1)
    runner = ConcurrentRunner(
        metadata_store=store,
        handler_registry=registry,
        executor=executor,
        clock=SystemClock(),
        id_factory=UuidRuntimeIdFactory(),
        sleeper=SystemSleeper(),
        global_limit=1,
    )

    try:
        run = runner.run(workflow)
    finally:
        executor.shutdown()

    task_run = store.list_task_runs(run.run_id)[0]
    attempt = store.list_task_attempts(task_run.task_run_id)[0]

    assert run.status is WorkflowRunStatus.FAILED
    assert task_run.status is TaskRunStatus.FAILED
    assert attempt.status is TaskAttemptStatus.FAILED
    assert attempt.error_type == "ExecutionTimeoutError"
    assert attempt.error_category == "timeout"
