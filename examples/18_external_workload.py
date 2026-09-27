"""Canonical atomic external-workload integration example."""

from __future__ import annotations

import json

from pyworkflowkit import TaskHandle, WorkflowRuntime, workflow
from pyworkflowkit.ecosystem import (
    ExternalWorkloadResult,
    RunContext,
    external_workload_task,
)


class ExampleRemoteJob:
    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        return ExternalWorkloadResult(
            external_run_id=f"remote-{context.task_run_id}",
            succeeded=True,
            output={"rows": 3},
            metadata={"service": "example"},
        )


remote_job = external_workload_task(
    id="remote_job",
    provider="example",
    workload_ref="jobs/daily",
    workload=ExampleRemoteJob(),
)


@workflow(id="examples.external-workload", version="1")
def demo() -> tuple[TaskHandle, ...]:
    return (remote_job,)


runtime = WorkflowRuntime()
runtime.register(remote_job.handler_ref, remote_job.handler)

definition = demo.build()
run = runtime.run(definition)
lineage = runtime.lineage(definition, run.run_id)

print(
    json.dumps(
        {
            "external_reference_count": sum(len(task.external_ref_ids) for task in lineage.tasks),
            "status": run.status.value,
        },
        sort_keys=True,
    )
)
