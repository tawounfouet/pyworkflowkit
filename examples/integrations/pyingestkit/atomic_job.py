"""Canonical PyIngestKit anti-corruption example.

No concrete PyIngestKit package is required: the external wrapper implements the small
adapter protocol and returns the normalized boundary result expected by PyWorkflowKit.
"""

from __future__ import annotations

import json

from pyworkflowkit import TaskHandle, WorkflowRuntime, workflow
from pyworkflowkit.ecosystem import RunContext
from pyworkflowkit.integrations.pyingestkit import (
    PyIngestKitRunResult,
    pyingestkit_task,
)


class ExamplePyIngestKitJob:
    def run(self, *, context: RunContext) -> PyIngestKitRunResult:
        return PyIngestKitRunResult(
            external_run_id=f"ingest-{context.task_run_id}",
            succeeded=True,
            output={"rows": 3},
            metadata={"job": "daily-customers"},
        )


ingest = pyingestkit_task(
    id="ingest",
    job_ref="daily-customers",
    job=ExamplePyIngestKitJob(),
)


@workflow(id="examples.pyingestkit", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (ingest,)


runtime = WorkflowRuntime()
runtime.register(ingest.handler_ref, ingest.handler)

definition = demo.build()
run = runtime.run(definition)
lineage = runtime.lineage(definition, run.run_id)

print(
    json.dumps(
        {
            "external_reference_count": sum(
                len(task.external_ref_ids) for task in lineage.tasks
            ),
            "status": run.status.value,
        },
        sort_keys=True,
    )
)
