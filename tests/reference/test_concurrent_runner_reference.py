"""M29 ConcurrentRunner reference acceptance coverage."""

import threading

from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.concurrent_runner import ConcurrentRunner
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import TaskRunStatus, WorkflowRunStatus
from pyworkflowkit.domain.ids import TaskId, WorkflowId
from pyworkflowkit.ports.executor import RunContext


def test_diamond_executes_siblings_concurrently_before_fan_in() -> None:
    barrier = threading.Barrier(2)
    registry = HandlerRegistry()

    registry.register("handlers:A", lambda: "root")

    def sibling(context: RunContext) -> str:
        barrier.wait(timeout=2.0)
        return str(context.task_id)

    registry.register("handlers:B", sibling)
    registry.register("handlers:C", sibling)
    registry.register(
        "handlers:D",
        lambda context: (
            context.dependency_outputs[TaskId("B")],
            context.dependency_outputs[TaskId("C")],
        ),
    )

    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("reference.concurrent"),
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
                depends_on=(TaskId("A"),),
                executor_key="thread",
            ),
            TaskDefinition(
                task_id=TaskId("C"),
                handler_ref="handlers:C",
                depends_on=(TaskId("A"),),
                executor_key="thread",
            ),
            TaskDefinition(
                task_id=TaskId("D"),
                handler_ref="handlers:D",
                depends_on=(TaskId("B"), TaskId("C")),
                executor_key="thread",
            ),
        ),
    )

    store = MemoryMetadataStore()
    executor = ThreadExecutor(max_workers=2)
    runner = ConcurrentRunner(
        metadata_store=store,
        handler_registry=registry,
        executor=executor,
        clock=SystemClock(),
        id_factory=UuidRuntimeIdFactory(),
        sleeper=SystemSleeper(),
        global_limit=2,
    )

    try:
        run = runner.run(workflow)
    finally:
        executor.shutdown()

    assert run.status is WorkflowRunStatus.SUCCEEDED
    assert {task_run.status for task_run in store.list_task_runs(run.run_id)} == {
        TaskRunStatus.SUCCEEDED
    }
