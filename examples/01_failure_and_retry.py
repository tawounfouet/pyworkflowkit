"""Public-API failure and retry example."""

from __future__ import annotations

import json

from pyworkflowkit._compat.v1_root import (
    BackoffStrategy,
    RetryPolicy,
    TaskHandle,
    WorkflowRuntime,
    task,
    workflow,
)

calls = 0


@task(
    retry_policy=RetryPolicy(
        max_attempts=2,
        backoff_strategy=BackoffStrategy.NONE,
        retryable_error_categories=frozenset({"RuntimeError"}),
    )
)
def unstable() -> str:
    global calls
    calls += 1
    if calls == 1:
        raise RuntimeError("temporary failure")
    return "recovered"


@workflow(id="docs.retry", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (unstable,)


runtime = WorkflowRuntime()
for handle in demo.task_handles():
    runtime.register(handle.handler_ref, handle.handler)

run = runtime.run(demo.build())
event_types = [event.event_type.value for event in runtime.events(run.run_id)]

print(
    json.dumps(
        {
            "status": run.status.value,
            "attempts": calls,
            "retry_event_observed": "TASK_RETRYING" in event_types,
        },
        sort_keys=True,
    )
)
