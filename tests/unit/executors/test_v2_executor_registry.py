"""LOT-13 unit tests for the canonical V2 ExecutorRegistry."""

from __future__ import annotations

import pytest

from pyworkflowkit.errors import ExecutorNotFoundError
from pyworkflowkit.executors import ExecutorRegistry, InlineExecutor, ThreadExecutor


def test_registry_resolves_registered_executors_deterministically() -> None:
    inline = InlineExecutor()
    thread = ThreadExecutor(max_workers=1)
    try:
        registry = ExecutorRegistry((thread, inline))

        assert registry.executor_ids == ("inline", "thread")
        assert registry.resolve("inline") is inline
        assert registry.resolve("thread") is thread
        assert tuple(item.executor_id for item in registry.descriptors()) == (
            "inline",
            "thread",
        )
    finally:
        thread.shutdown()


def test_registry_duplicate_executor_id_is_rejected() -> None:
    registry = ExecutorRegistry((InlineExecutor(),))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(InlineExecutor())


def test_registry_same_instance_registration_is_idempotent() -> None:
    inline = InlineExecutor()
    registry = ExecutorRegistry((inline,))

    registry.register(inline)

    assert registry.executor_ids == ("inline",)


def test_registry_missing_executor_is_explicit() -> None:
    registry = ExecutorRegistry((InlineExecutor(),))

    with pytest.raises(ExecutorNotFoundError):
        registry.resolve("thread")


@pytest.mark.parametrize("executor_id", ["", "   "])
def test_registry_rejects_blank_resolution_key(executor_id: str) -> None:
    with pytest.raises(ValueError, match="executor_id"):
        ExecutorRegistry().resolve(executor_id)


def test_registry_rejects_non_executor_values() -> None:
    registry = ExecutorRegistry()

    with pytest.raises(TypeError, match="Executor Protocol"):
        registry.register(object())  # type: ignore[arg-type]
