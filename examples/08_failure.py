"""Canonical terminal failure example with an expected public exception."""

from __future__ import annotations

import json

from pyworkflowkit._compat.v1_root import PyWorkflowKitError, TaskHandle, WorkflowRuntime, task, workflow


@task
def fail() -> str:
    raise ValueError("expected example failure")


@workflow(id="examples.failure", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (fail,)


runtime = WorkflowRuntime()
runtime.register(fail.handler_ref, fail.handler)

try:
    runtime.run(demo.build())
except PyWorkflowKitError as exc:
    print(
        json.dumps(
            {
                "error": type(exc).__name__,
                "handled": True,
            },
            sort_keys=True,
        )
    )
else:
    raise RuntimeError("the failure example unexpectedly succeeded")
