"""M18 public API acceptance coverage."""

from pyworkflowkit import (
    BackoffStrategy,
    RetryPolicy,
    TaskDefinition,
    TaskId,
    TaskResult,
    WorkflowDefinition,
    WorkflowId,
    WorkflowRuntime,
)


def test_public_api_can_execute_workflow_end_to_end() -> None:
    runtime = WorkflowRuntime()
    runtime.register("handlers:hello", lambda: TaskResult(output="hello"))

    workflow = WorkflowDefinition(
        workflow_id=WorkflowId("public-api"),
        version="1",
        tasks=(
            TaskDefinition(
                task_id=TaskId("hello"),
                handler_ref="handlers:hello",
                retry_policy=RetryPolicy(
                    max_attempts=1,
                    backoff_strategy=BackoffStrategy.NONE,
                ),
            ),
        ),
    )

    run = runtime.run(workflow)
    loaded = runtime.get_run(run.run_id)
    events = runtime.events(run.run_id)
    manifest = runtime.manifest(workflow, run.run_id)
    lineage = runtime.lineage(workflow, run.run_id)

    assert loaded.run_id == run.run_id
    assert events
    assert manifest.run_id == str(run.run_id)
    assert lineage.run_id == str(run.run_id)


def test_root_import_surface_is_intentional() -> None:
    import pyworkflowkit

    expected = {
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
        "task",
        "workflow",
        "__version__",
    }

    assert set(pyworkflowkit.__all__) == expected
