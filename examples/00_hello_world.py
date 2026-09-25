"""Minimal executable PyWorkflowKit 0.1 alpha example."""

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.adapters.runtime import SystemClock, SystemSleeper, UuidRuntimeIdFactory
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.manifest import RunManifestBuilder, RunManifestSerializer
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.ids import TaskId, WorkflowId
from pyworkflowkit.ports.executor import RunContext


def fetch() -> list[int]:
    return [1, 2, 3]


def transform(context: RunContext) -> list[int]:
    values = context.dependency_outputs[TaskId("fetch")]
    if not isinstance(values, list):
        raise TypeError("fetch output must be a list")
    return [int(value) * 10 for value in values]


workflow = WorkflowDefinition(
    workflow_id=WorkflowId("hello-world"),
    version="1",
    tasks=(
        TaskDefinition(
            task_id=TaskId("fetch"),
            handler_ref="handlers:fetch",
        ),
        TaskDefinition(
            task_id=TaskId("transform"),
            handler_ref="handlers:transform",
            depends_on=(TaskId("fetch"),),
        ),
    ),
)

handlers = HandlerRegistry()
handlers.register("handlers:fetch", fetch)
handlers.register("handlers:transform", transform)

store = MemoryMetadataStore()
runner = Runner(
    metadata_store=store,
    handler_registry=handlers,
    executor=LocalExecutor(),
    clock=SystemClock(),
    id_factory=UuidRuntimeIdFactory(),
    sleeper=SystemSleeper(),
)

run = runner.run(workflow)
manifest = RunManifestBuilder(metadata_store=store).build(
    workflow=workflow,
    run_id=run.run_id,
)

print(RunManifestSerializer().to_json(manifest))
