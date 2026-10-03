"""M47 reference acceptance for external workload interoperability."""

from __future__ import annotations

from dataclasses import dataclass

from pyworkflowkit._compat.v1_root import RetryPolicy, TaskHandle, WorkflowRuntime, workflow
from pyworkflowkit.domain.enums import RuntimeEventType
from pyworkflowkit.integrations.workload import (
    EXTERNAL_WORKLOAD_CONTRACT_VERSION,
    ExternalRetryOwner,
    ExternalWorkloadResult,
    external_workload_task,
)
from pyworkflowkit.ports.executor import RunContext


@dataclass
class ReferenceWorkload:
    attempts: int = 0

    def run(self, *, context: RunContext) -> ExternalWorkloadResult:
        self.attempts += 1
        return ExternalWorkloadResult(
            external_run_id=f"foreign-{context.workflow_run_id}",
            succeeded=True,
            output={"attempt": self.attempts},
            uri="acme://runs/reference",
            metadata={"source": "reference"},
        )


def test_external_workload_is_one_atomic_task_with_portable_evidence() -> None:
    workload = ReferenceWorkload()
    external = external_workload_task(
        id="external",
        provider="acme",
        workload_ref="reference.job",
        workload=workload,
    )

    @workflow(id="integration.external-workload", version="1")
    def demo() -> tuple[TaskHandle, ...]:
        return (external,)

    runtime = WorkflowRuntime()
    runtime.register(external.handler_ref, external.handler)

    definition = demo.build()
    run = runtime.run(definition)
    manifest = runtime.manifest(definition, run.run_id)
    lineage = runtime.lineage(definition, run.run_id)

    assert EXTERNAL_WORKLOAD_CONTRACT_VERSION == "1"
    assert run.status.value == "SUCCEEDED"
    assert workload.attempts == 1
    assert len(manifest.tasks) == 1
    assert manifest.tasks[0].external_refs[0].provider == "acme"
    assert manifest.tasks[0].external_refs[0].external_run_id.startswith("foreign-")
    assert lineage.tasks[0].external_ref_ids


def test_pyworkflowkit_retry_ownership_preserves_external_failure_category() -> None:
    @dataclass
    class FlakyWorkload:
        attempts: int = 0

        def run(self, *, context: RunContext) -> ExternalWorkloadResult:
            self.attempts += 1
            if self.attempts == 1:
                return ExternalWorkloadResult(
                    external_run_id="foreign-retry",
                    succeeded=False,
                    error_type="RemoteTemporaryError",
                    error_message="try again",
                    error_category="temporary",
                )
            return ExternalWorkloadResult(
                external_run_id="foreign-retry",
                succeeded=True,
                output="recovered",
            )

    workload = FlakyWorkload()
    external = external_workload_task(
        id="external",
        provider="acme",
        workload_ref="reference.retry",
        workload=workload,
        retry_owner=ExternalRetryOwner.PYWORKFLOWKIT,
        retry_policy=RetryPolicy(
            max_attempts=2,
            retryable_error_categories=frozenset({"temporary"}),
        ),
    )

    @workflow(id="integration.external-retry", version="1")
    def demo() -> tuple[TaskHandle, ...]:
        return (external,)

    runtime = WorkflowRuntime()
    runtime.register(external.handler_ref, external.handler)

    definition = demo.build()
    run = runtime.run(definition)
    events = runtime.events(run.run_id)

    assert run.status.value == "SUCCEEDED"
    assert workload.attempts == 2
    assert RuntimeEventType.TASK_RETRYING in {event.event_type for event in events}


def test_m47_does_not_expand_package_root_api() -> None:
    import pyworkflowkit

    assert "ExternalWorkload" not in pyworkflowkit.__all__
    assert "external_workload_task" not in pyworkflowkit.__all__
