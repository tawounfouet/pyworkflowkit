"""M26 capacity-model acceptance coverage."""

from pyworkflowkit.application.capacity import CapacityManager
from pyworkflowkit.domain.ids import TaskAttemptId
from pyworkflowkit.ports.executor import ExecutorCapabilities


def test_capacity_manager_bounds_global_and_per_executor_attempts() -> None:
    manager = CapacityManager(
        global_limit=3,
        executor_capabilities={
            "local": ExecutorCapabilities(max_concurrency=1),
            "thread": ExecutorCapabilities(
                supports_parallelism=True,
                max_concurrency=4,
            ),
        },
        per_executor_limits={"thread": 2},
    )

    local = manager.try_acquire(
        executor_key="local",
        attempt_id=TaskAttemptId("local-1"),
    )
    thread_one = manager.try_acquire(
        executor_key="thread",
        attempt_id=TaskAttemptId("thread-1"),
    )
    thread_two = manager.try_acquire(
        executor_key="thread",
        attempt_id=TaskAttemptId("thread-2"),
    )

    assert local is not None
    assert thread_one is not None
    assert thread_two is not None
    assert (
        manager.try_acquire(
            executor_key="thread",
            attempt_id=TaskAttemptId("thread-3"),
        )
        is None
    )

    manager.release(thread_one)

    replacement = manager.try_acquire(
        executor_key="thread",
        attempt_id=TaskAttemptId("thread-3"),
    )

    assert replacement is not None
    assert manager.snapshot().active_attempts == 3
