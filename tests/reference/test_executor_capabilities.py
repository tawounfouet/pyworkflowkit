"""M25 executor capability acceptance coverage."""

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.ports.executor import (
    CancellationCapability,
    TimeoutCapability,
)


def test_local_executor_declares_conservative_single_slot_capabilities() -> None:
    capabilities = LocalExecutor().capabilities

    assert capabilities.supports_parallelism is False
    assert capabilities.max_concurrency == 1
    assert capabilities.timeout is TimeoutCapability.NONE
    assert capabilities.cancellation is CancellationCapability.NONE
    assert capabilities.supports_timeout is False
    assert capabilities.supports_cancellation is False
