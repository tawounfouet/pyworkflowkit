"""M28 ThreadExecutor reference acceptance coverage."""

import threading

from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.domain.definitions import TaskDefinition
from pyworkflowkit.domain.ids import TaskAttemptId, TaskId, TaskRunId, WorkflowRunId
from pyworkflowkit.ports.executor import RunContext, TimeoutCapability


def _context(name: str) -> RunContext:
    return RunContext(
        workflow_run_id=WorkflowRunId("reference-run"),
        task_run_id=TaskRunId(f"task-run-{name}"),
        attempt_id=TaskAttemptId(f"attempt-{name}"),
        task_id=TaskId(name),
        attempt_number=1,
    )


def test_thread_executor_parallelism_completion_soft_timeout_and_shutdown() -> None:
    executor = ThreadExecutor(max_workers=2)
    release = threading.Event()
    entered = threading.Barrier(3)

    def handler(context: RunContext) -> str:
        entered.wait(timeout=1.0)
        release.wait(timeout=1.0)
        return str(context.task_id)

    try:
        handles = tuple(
            executor.submit(
                task=TaskDefinition(
                    task_id=TaskId(name),
                    handler_ref=f"handlers:{name}",
                    executor_key="thread",
                ),
                handler=handler,
                context=_context(name),
            )
            for name in ("a", "b")
        )

        entered.wait(timeout=1.0)

        assert executor.capabilities.supports_parallelism is True
        assert executor.capabilities.timeout is TimeoutCapability.SOFT
        assert executor.wait(handles[0], timeout=0) is False
        assert len(executor.active_handles()) == 2

        release.set()

        completions = (
            executor.completion_queue.get(timeout=1.0),
            executor.completion_queue.get(timeout=1.0),
        )
        assert {completion.handle for completion in completions} == set(handles)
        assert all(completion.succeeded for completion in completions)
    finally:
        release.set()
        executor.shutdown(wait=True)

    assert executor.is_shutdown is True
