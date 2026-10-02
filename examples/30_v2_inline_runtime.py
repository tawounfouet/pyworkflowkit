"""First end-to-end PyWorkflowKit V2 local runtime example."""

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.executors import InlineExecutor, TaskExecutionContext
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.runtime import WorkflowRuntime


def extract() -> int:
    return 21


def transform(context: TaskExecutionContext) -> int:
    return int(context.dependency_outputs["extract"]) * 2


workflow = WorkflowDefinition(
    name="v2-inline-example",
    tasks=(
        TaskDefinition(
            key="extract",
            workload=extract,
        ),
        TaskDefinition(
            key="transform",
            workload=transform,
            dependencies=("extract",),
        ),
    ),
)

runtime = WorkflowRuntime(
    executor=InlineExecutor(),
    metadata=InMemoryMetadataStore(),
)

result = runtime.run(workflow)

assert result.status.value == "SUCCEEDED"
assert result.task("transform").output == 42

print(result.run_id)
print(result.status.value)
print(result.task("transform").output)
