"""M21 runtime observability acceptance coverage."""

import logging

from pyworkflowkit import (
    BackoffStrategy,
    RetryPolicy,
    TaskHandle,
    WorkflowParameter,
    WorkflowRuntime,
    task,
    workflow,
)
from pyworkflowkit.application.observability import structured_fields


def test_runtime_emits_correlated_logs_without_parameter_secrets(caplog) -> None:  # type: ignore[no-untyped-def]
    calls = 0

    @task(
        retry_policy=RetryPolicy(
            max_attempts=2,
            backoff_strategy=BackoffStrategy.NONE,
            retryable_error_categories=frozenset({"RuntimeError"}),
        )
    )
    def unstable() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary failure")
        return "ok"

    @workflow(
        id="observability.demo",
        version="1",
        parameters=(
            WorkflowParameter(
                name="api_token",
                required=True,
                sensitive=True,
            ),
        ),
    )
    def demo() -> tuple[TaskHandle, ...]:
        return (unstable,)

    runtime = WorkflowRuntime()
    for handle in demo.task_handles():
        runtime.register(handle.handler_ref, handle.handler)

    with caplog.at_level(logging.DEBUG, logger="pyworkflowkit"):
        run = runtime.run(demo.build(), parameters={"api_token": "super-secret"})

    messages = [record.getMessage() for record in caplog.records]
    assert "Workflow run created" in messages
    assert "Task attempt failed" in messages
    assert "Retry scheduled" in messages
    assert "Workflow run succeeded" in messages
    assert "super-secret" not in caplog.text

    correlated = [
        structured_fields(record)
        for record in caplog.records
        if structured_fields(record).get("run_id") == str(run.run_id)
    ]
    assert correlated
    assert any(fields.get("task_id") == "unstable" for fields in correlated)
