"""Tests for M26 capacity accounting."""

import threading

import pytest

from pyworkflowkit.application.capacity import CapacityManager
from pyworkflowkit.domain.ids import TaskAttemptId
from pyworkflowkit.errors import (
    CapacityConfigurationError,
    CapacityInvariantError,
    CapacityReleaseError,
)
from pyworkflowkit.ports.executor import ExecutorCapabilities


def _manager(
    *,
    global_limit: int = 3,
    local_limit: int = 1,
    thread_limit: int = 2,
) -> CapacityManager:
    return CapacityManager(
        global_limit=global_limit,
        executor_capabilities={
            "local": ExecutorCapabilities(max_concurrency=1),
            "thread": ExecutorCapabilities(
                supports_parallelism=True,
                max_concurrency=thread_limit,
            ),
        },
        per_executor_limits={
            "local": local_limit,
            "thread": thread_limit,
        },
    )


def test_capacity_manager_applies_global_and_executor_limits() -> None:
    manager = _manager(global_limit=3, thread_limit=2)

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

    snapshot = manager.snapshot()
    assert snapshot.active_attempts == 3
    assert snapshot.available_global_slots == 0
    assert snapshot.executors["local"].active == 1
    assert snapshot.executors["local"].available == 0
    assert snapshot.executors["thread"].active == 2
    assert snapshot.executors["thread"].available == 0


def test_configured_limit_cannot_exceed_executor_intrinsic_capacity() -> None:
    manager = CapacityManager(
        global_limit=10,
        executor_capabilities={
            "thread": ExecutorCapabilities(
                supports_parallelism=True,
                max_concurrency=4,
            )
        },
        per_executor_limits={"thread": 8},
    )

    assert manager.snapshot().executors["thread"].limit == 4


def test_release_returns_capacity_to_both_counters() -> None:
    manager = _manager()
    lease = manager.try_acquire(
        executor_key="thread",
        attempt_id=TaskAttemptId("attempt-1"),
    )
    assert lease is not None

    manager.release(lease)

    snapshot = manager.snapshot()
    assert snapshot.active_attempts == 0
    assert snapshot.executors["thread"].active == 0
    assert snapshot.executors["thread"].available == 2


def test_duplicate_active_attempt_is_rejected() -> None:
    manager = _manager()
    attempt_id = TaskAttemptId("attempt-1")

    assert manager.try_acquire(executor_key="thread", attempt_id=attempt_id) is not None

    with pytest.raises(CapacityInvariantError, match="already owns"):
        manager.try_acquire(executor_key="thread", attempt_id=attempt_id)


def test_release_unknown_attempt_is_rejected() -> None:
    manager = _manager()
    from pyworkflowkit.application.capacity import CapacityLease

    with pytest.raises(CapacityReleaseError, match="does not own"):
        manager.release(
            CapacityLease(
                attempt_id=TaskAttemptId("missing"),
                executor_key="thread",
            )
        )


def test_unknown_executor_is_rejected() -> None:
    manager = _manager()

    with pytest.raises(CapacityConfigurationError, match="no registered"):
        manager.try_acquire(
            executor_key="unknown",
            attempt_id=TaskAttemptId("attempt-1"),
        )


def test_active_attempts_are_reported_deterministically() -> None:
    manager = _manager(global_limit=3, thread_limit=2)

    assert (
        manager.try_acquire(
            executor_key="thread",
            attempt_id=TaskAttemptId("z"),
        )
        is not None
    )
    assert (
        manager.try_acquire(
            executor_key="local",
            attempt_id=TaskAttemptId("a"),
        )
        is not None
    )

    assert [str(lease.attempt_id) for lease in manager.active_attempts()] == ["a", "z"]


def test_capacity_accounting_is_thread_safe() -> None:
    manager = CapacityManager(
        global_limit=2,
        executor_capabilities={
            "thread": ExecutorCapabilities(
                supports_parallelism=True,
                max_concurrency=2,
            )
        },
    )
    barrier = threading.Barrier(6)
    acquired: list[str] = []
    acquired_lock = threading.Lock()

    def worker(index: int) -> None:
        barrier.wait()
        lease = manager.try_acquire(
            executor_key="thread",
            attempt_id=TaskAttemptId(f"attempt-{index}"),
        )
        if lease is not None:
            with acquired_lock:
                acquired.append(str(lease.attempt_id))

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(acquired) == 2
    assert manager.snapshot().active_attempts == 2
