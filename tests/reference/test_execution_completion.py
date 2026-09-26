"""M27 execution-handle and completion acceptance coverage."""

from pyworkflowkit.application.completion import (
    AttemptCompletion,
    CompletionQueue,
    ExecutionHandle,
)
from pyworkflowkit.domain.ids import TaskAttemptId
from pyworkflowkit.domain.values import TaskResult


def test_worker_completion_can_be_transferred_without_state_transition() -> None:
    queue = CompletionQueue()
    handle = ExecutionHandle(
        handle_id="thread:attempt-1",
        attempt_id=TaskAttemptId("attempt-1"),
        executor_key="thread",
    )

    queue.put(
        AttemptCompletion(
            handle=handle,
            result=TaskResult(output={"status": "done"}),
        )
    )

    completion = queue.get_nowait()

    assert completion is not None
    assert completion.handle == handle
    assert completion.succeeded is True
    assert completion.result is not None
    assert completion.result.output == {"status": "done"}
