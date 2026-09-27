"""Canonical timeout declaration and capability example."""

from __future__ import annotations

import json

from pyworkflowkit import TaskDefinition, TaskId, TimeoutMode
from pyworkflowkit.ecosystem import ExecutorCapabilities, TimeoutCapability


task_definition = TaskDefinition(
    task_id=TaskId("remote_call"),
    handler_ref="handlers:remote_call",
    timeout_seconds=5.0,
    timeout_mode=TimeoutMode.SOFT,
)

capabilities = ExecutorCapabilities(
    timeout=TimeoutCapability.SOFT,
)

print(
    json.dumps(
        {
            "executor_timeout_capability": capabilities.timeout.value,
            "task_timeout_mode": task_definition.timeout_mode.value,
            "timeout_seconds": task_definition.timeout_seconds,
        },
        sort_keys=True,
    )
)
