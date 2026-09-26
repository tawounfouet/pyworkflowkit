"""M24 PyIngestKit adapter acceptance coverage."""

from pyworkflowkit import TaskHandle, WorkflowRuntime, workflow
from pyworkflowkit.integrations.pyingestkit import (
    PyIngestKitRunResult,
    pyingestkit_task,
)
from pyworkflowkit.ports.executor import RunContext


class ReferenceIngestionJob:
    def run(self, *, context: RunContext) -> PyIngestKitRunResult:
        return PyIngestKitRunResult(
            external_run_id=f"ingest-{context.workflow_run_id}",
            succeeded=True,
            output={"row_count": 3},
            uri="pyingestkit://runs/reference",
            metadata={"job": "reference.ingestion"},
        )


def test_workflow_treats_pyingestkit_job_as_one_atomic_task() -> None:
    ingest = pyingestkit_task(
        id="ingest",
        job_ref="reference.ingestion",
        job=ReferenceIngestionJob(),
    )

    @workflow(id="integration.pyingestkit", version="1")
    def demo() -> tuple[TaskHandle, ...]:
        return (ingest,)

    runtime = WorkflowRuntime()
    runtime.register(ingest.handler_ref, ingest.handler)

    definition = demo.build()
    run = runtime.run(definition)
    manifest = runtime.manifest(definition, run.run_id)
    lineage = runtime.lineage(definition, run.run_id)

    assert run.status.value == "SUCCEEDED"
    assert len(manifest.tasks) == 1
    assert manifest.tasks[0].external_refs[0].provider == "pyingestkit"
    assert lineage.tasks[0].external_ref_ids
