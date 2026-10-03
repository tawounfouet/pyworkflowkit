"""Transverse 0.5.0 release-contract qualification."""

from __future__ import annotations

import pyworkflowkit._compat.v1_root as v1_root
from pyworkflowkit.adapters.executors.asyncio import AsyncExecutor
from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.executors.process import ProcessExecutor
from pyworkflowkit.adapters.executors.subprocess import SubprocessExecutor
from pyworkflowkit.adapters.executors.thread import ThreadExecutor
from pyworkflowkit.application.manifest import MANIFEST_SCHEMA_VERSION
from pyworkflowkit.plugins import PLUGIN_API_VERSION
from pyworkflowkit.ports.executor import CancellationCapability, TimeoutCapability

EXPECTED_PUBLIC_API = {
    "ArtifactId",
    "ArtifactReference",
    "BackoffStrategy",
    "ExternalRunRef",
    "ExternalRunRefId",
    "FailurePolicy",
    "PyWorkflowKitError",
    "RetryPolicy",
    "RunContext",
    "RuntimeSettings",
    "TaskDefinition",
    "TaskHandle",
    "TaskId",
    "TaskResult",
    "TimeoutMode",
    "WorkflowBuilder",
    "WorkflowDefinition",
    "WorkflowId",
    "WorkflowParameter",
    "WorkflowRuntime",
    "__version__",
    "task",
    "workflow",
}


def test_v0_5_executor_family_capability_matrix_is_frozen() -> None:
    local = LocalExecutor()
    with (
        ThreadExecutor(max_workers=3) as thread,
        ProcessExecutor(max_workers=2) as process,
        AsyncExecutor(max_concurrency=5) as async_executor,
        SubprocessExecutor(max_workers=4) as subprocess,
    ):
        actual = {
            local.key: local.capabilities,
            thread.key: thread.capabilities,
            process.key: process.capabilities,
            async_executor.key: async_executor.capabilities,
            subprocess.key: subprocess.capabilities,
        }

        assert set(actual) == {"local", "thread", "process", "async", "subprocess"}

        assert actual["local"].supports_parallelism is False
        assert actual["local"].timeout is TimeoutCapability.NONE
        assert actual["local"].cancellation is CancellationCapability.NONE
        assert actual["local"].max_concurrency == 1
        assert actual["local"].supports_async is False

        assert actual["thread"].supports_parallelism is True
        assert actual["thread"].timeout is TimeoutCapability.SOFT
        assert actual["thread"].cancellation is CancellationCapability.NONE
        assert actual["thread"].max_concurrency == 3
        assert actual["thread"].supports_async is False

        assert actual["process"].supports_parallelism is True
        assert actual["process"].timeout is TimeoutCapability.HARD
        assert actual["process"].cancellation is CancellationCapability.HARD
        assert actual["process"].max_concurrency == 2
        assert actual["process"].supports_async is False

        assert actual["async"].supports_parallelism is True
        assert actual["async"].timeout is TimeoutCapability.SOFT
        assert actual["async"].cancellation is CancellationCapability.COOPERATIVE
        assert actual["async"].max_concurrency == 5
        assert actual["async"].supports_async is True

        assert actual["subprocess"].supports_parallelism is True
        assert actual["subprocess"].timeout is TimeoutCapability.HARD
        assert actual["subprocess"].cancellation is CancellationCapability.HARD
        assert actual["subprocess"].max_concurrency == 4
        assert actual["subprocess"].supports_async is False


def test_v0_5_package_root_public_api_remains_intentionally_small() -> None:
    assert set(v1_root.__all__) == EXPECTED_PUBLIC_API
    assert "ThreadExecutor" not in v1_root.__all__
    assert "ProcessExecutor" not in v1_root.__all__
    assert "AsyncExecutor" not in v1_root.__all__
    assert "SubprocessExecutor" not in v1_root.__all__


def test_v0_5_portable_contract_versions_remain_compatible() -> None:
    assert MANIFEST_SCHEMA_VERSION == "1"
    assert PLUGIN_API_VERSION == "1"
