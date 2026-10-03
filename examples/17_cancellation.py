"""Canonical cancellation capability example."""

from __future__ import annotations

import json

from pyworkflowkit._compat.v1_root import WorkflowRuntime
from pyworkflowkit.control_plane import ControlPlaneOperation, WorkflowRuntimeProvider
from pyworkflowkit.ecosystem import CancellationCapability, ExecutorCapabilities

provider_capabilities = WorkflowRuntimeProvider(WorkflowRuntime()).inspect_capabilities()
cooperative_executor = ExecutorCapabilities(
    supports_parallelism=True,
    cancellation=CancellationCapability.COOPERATIVE,
    max_concurrency=4,
)

print(
    json.dumps(
        {
            "executor_cancellation": cooperative_executor.cancellation.value,
            "provider_request_cancellation": provider_capabilities.operations[
                ControlPlaneOperation.REQUEST_CANCELLATION.value
            ],
        },
        sort_keys=True,
    )
)
