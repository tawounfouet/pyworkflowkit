"""M30 cancellation reference acceptance coverage."""

import threading

from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.cancellation import CancellationController
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import RuntimeEventType, TaskRunStatus, WorkflowRunStatus
from pyworkflowkit.domain.ids import TaskId, WorkflowId


def test_cancellation_stops_new_dispatch_and_drains_running_work() -> None:
    started = threading.Event()
    release = threading.Event()
    cancellation = CancellationController()
    registry = HandlerRegistry()

    def running() -> str:
        started.set()
        release.wait(timeout=2.0)
        return "done"

    registry.register("handlers:A", running)
    registry.register("handlers:B", lambda: "must-not-run")

    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.cancellation"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("A"),
                handler_ref="handlers:A",
                executor_key="thread",
            ),
            TaskDefinition(
                task_id=TaskId("B"),
                handler_ref="handlers:B",
                executor_key="thread",
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
    result = []

    thread = threading.Thread(
        target=lambda: result.append(runner.run(workflow, cancellation=cancellation))
    )
    thread.start()
    assert started.wait(timeout=2.0) is True

    cancellation.request(reason="reference-request")
    release.set()
    thread.join(timeout=3.0)

    try:
        assert thread.is_alive() is False
        run = result[0]
        task_runs = {task.task_id: task for task in store.list_task_runs(run.run_id)}
        events = store.list_events(run.run_id)

        assert run.status is WorkflowRunStatus.CANCELLED
        assert task_runs[TaskId("A")].status is TaskRunStatus.SUCCEEDED
        assert task_runs[TaskId("B")].status is TaskRunStatus.CANCELLED
        assert any(
            event.event_type is RuntimeEventType.WORKFLOW_CANCELLED
            and event.payload["reason"] == "reference-request"
            for event in events
        )
    finally:
        release.set()
        executor.shutdown(wait=True)
