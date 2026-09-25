"""Tests for final deterministic RunManifest evidence."""

from collections.abc import Mapping
from datetime import UTC, datetime

import pytest

from pyworkflowkit.adapters.executors.local import LocalExecutor
from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore
from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.application.manifest import (
    MANIFEST_SCHEMA_VERSION,
    REDACTED_VALUE,
    RunManifestBuilder,
    RunManifestSerializer,
)
from pyworkflowkit.application.runner import Runner
from pyworkflowkit.domain.definitions import TaskDefinition, WorkflowDefinition
from pyworkflowkit.domain.enums import SkipReason, TaskRunStatus, WorkflowRunStatus
from pyworkflowkit.domain.ids import (
    ArtifactId,
    ExternalRunRefId,
    RuntimeEventId,
    TaskAttemptId,
    TaskId,
    TaskRunId,
    WorkflowId,
    WorkflowRunId,
)
from pyworkflowkit.domain.runtime import WorkflowRun
from pyworkflowkit.domain.values import (
    ArtifactReference,
    ExternalRunRef,
    RetryPolicy,
    TaskResult,
    WorkflowParameter,
)
from pyworkflowkit.errors import (
    ManifestInvariantError,
    ManifestNotReadyError,
    ManifestSerializationError,
    TaskExecutionError,
)
from pyworkflowkit.ports.executor import RunContext

NOW = datetime(2026, 9, 25, 22, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


class NoopSleeper:
    def sleep(self, seconds: float) -> None:
        del seconds


class DeterministicIdFactory:
    def new_workflow_run_id(self) -> WorkflowRunId:
        return WorkflowRunId("workflow-run-1")

    def new_task_run_id(
        self,
        *,
        run_id: WorkflowRunId,
        task_id: TaskId,
    ) -> TaskRunId:
        return TaskRunId(f"{run_id}:{task_id}")

    def new_task_attempt_id(
        self,
        *,
        task_run_id: TaskRunId,
        attempt_number: int,
    ) -> TaskAttemptId:
        return TaskAttemptId(f"{task_run_id}:attempt-{attempt_number}")

    def new_runtime_event_id(
        self,
        *,
        run_id: WorkflowRunId,
        event_sequence: int,
    ) -> RuntimeEventId:
        return RuntimeEventId(f"{run_id}:event-{event_sequence}")


def task(
    task_id: str,
    *depends_on: str,
    retry_policy: RetryPolicy | None = None,
) -> TaskDefinition:
    return TaskDefinition(
        task_id=TaskId(task_id),
        handler_ref=f"handlers:{task_id}",
        depends_on=tuple(TaskId(value) for value in depends_on),
        retry_policy=retry_policy or RetryPolicy(),
    )


def workflow(
    *tasks: TaskDefinition,
    parameters: tuple[WorkflowParameter, ...] = (),
) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id=WorkflowId("workflow"),
        version="1",
        tasks=tasks,
        parameters=parameters,
    )


def runtime(
    handlers: Mapping[str, object],
) -> tuple[Runner, MemoryMetadataStore]:
    store = MemoryMetadataStore()
    registry = HandlerRegistry()
    for handler_ref, handler in handlers.items():
        registry.register(handler_ref, handler)  # type: ignore[arg-type]

    return (
        Runner(
            metadata_store=store,
            handler_registry=registry,
            executor=LocalExecutor(),
            clock=FixedClock(),
            id_factory=DeterministicIdFactory(),
            sleeper=NoopSleeper(),
        ),
        store,
    )


def test_manifest_captures_retry_artifact_external_ref_and_sensitive_redaction() -> None:
    calls = 0

    def fetch(context: RunContext) -> TaskResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        assert context.workflow_parameters["secret"] == "super-secret"
        return TaskResult(
            output="done",
            artifacts=(
                ArtifactReference(
                    artifact_id=ArtifactId("artifact-1"),
                    name="output.csv",
                    uri="file:///tmp/output.csv",
                    media_type="text/csv",
                    checksum="sha256:abc",
                    size_bytes=42,
                    metadata={"rows": 3},
                ),
            ),
            external_refs=(
                ExternalRunRef(
                    external_ref_id=ExternalRunRefId("external-1"),
                    provider="pyingestkit",
                    external_run_id="job-1",
                    metadata={"source": "ingestion"},
                ),
            ),
        )

    definition = workflow(
        task("fetch", retry_policy=RetryPolicy(max_attempts=2)),
        parameters=(
            WorkflowParameter(name="source"),
            WorkflowParameter(name="secret", sensitive=True),
        ),
    )
    runner, store = runtime({"handlers:fetch": fetch})

    run = runner.run(
        definition,
        parameters={
            "source": "input.csv",
            "secret": "super-secret",
        },
    )

    manifest = RunManifestBuilder(metadata_store=store).build(
        workflow=definition,
        run_id=run.run_id,
    )
    serialized = RunManifestSerializer().to_json(manifest)

    assert manifest.schema_version == MANIFEST_SCHEMA_VERSION
    assert manifest.status == WorkflowRunStatus.SUCCEEDED.value
    assert manifest.parameters == {
        "secret": REDACTED_VALUE,
        "source": "input.csv",
    }
    assert "super-secret" not in serialized
    assert tuple(attempt.attempt_number for attempt in manifest.tasks[0].attempts) == (
        1,
        2,
    )
    assert manifest.tasks[0].attempts[0].error_type == "TimeoutError"
    assert manifest.tasks[0].artifacts[0].artifact_id == "artifact-1"
    assert manifest.tasks[0].external_refs[0].external_run_id == "job-1"


def test_manifest_is_deterministic_across_repeated_reconstruction() -> None:
    definition = workflow(task("B", "A"), task("A"))
    runner, store = runtime(
        {
            "handlers:A": lambda: "a",
            "handlers:B": lambda: "b",
        }
    )
    run = runner.run(definition)
    builder = RunManifestBuilder(metadata_store=store)
    serializer = RunManifestSerializer()

    first = serializer.to_json(builder.build(workflow=definition, run_id=run.run_id))
    second = serializer.to_json(builder.build(workflow=definition, run_id=run.run_id))

    assert first == second
    assert '"generated_at"' not in first
    assert first.startswith('{"created_at":')


def test_manifest_failure_captures_failed_and_skipped_task_outcomes() -> None:
    def failing() -> None:
        raise ValueError("boom")

    definition = workflow(
        task("C", "B"),
        task("B", "A"),
        task("A"),
    )
    runner, store = runtime(
        {
            "handlers:A": failing,
            "handlers:B": lambda: None,
            "handlers:C": lambda: None,
        }
    )

    with pytest.raises(TaskExecutionError):
        runner.run(definition)

    manifest = RunManifestBuilder(metadata_store=store).build(
        workflow=definition,
        run_id=WorkflowRunId("workflow-run-1"),
    )
    tasks = {task_manifest.task_id: task_manifest for task_manifest in manifest.tasks}

    assert manifest.status == WorkflowRunStatus.FAILED.value
    assert tasks["A"].status == TaskRunStatus.FAILED.value
    assert tasks["B"].status == TaskRunStatus.SKIPPED.value
    assert tasks["B"].skip_reason == SkipReason.DEPENDENCY_FAILED.value
    assert tasks["C"].status == TaskRunStatus.SKIPPED.value
    assert manifest.events[-1].event_type == "WORKFLOW_FAILED"


def test_manifest_rejects_non_terminal_run() -> None:
    store = MemoryMetadataStore()
    pending = WorkflowRun(
        run_id=WorkflowRunId("pending-run"),
        workflow_id=WorkflowId("workflow"),
        workflow_version="1",
        created_at=NOW,
    )
    with store.unit_of_work() as uow:
        uow.add_workflow_run(pending)
        uow.commit()

    definition = workflow(task("A"))

    with pytest.raises(ManifestNotReadyError) as exc_info:
        RunManifestBuilder(metadata_store=store).build(
            workflow=definition,
            run_id=pending.run_id,
        )

    assert exc_info.value.status == WorkflowRunStatus.PENDING.value


def test_manifest_rejects_non_json_portable_parameter_value() -> None:
    class Unsupported:
        pass

    definition = workflow(
        task("A"),
        parameters=(WorkflowParameter(name="value"),),
    )
    runner, store = runtime({"handlers:A": lambda: None})
    run = runner.run(definition, parameters={"value": Unsupported()})

    with pytest.raises(ManifestSerializationError) as exc_info:
        RunManifestBuilder(metadata_store=store).build(
            workflow=definition,
            run_id=run.run_id,
        )

    assert exc_info.value.path == "parameters.value"
    assert exc_info.value.value_type == "Unsupported"


def test_manifest_rejects_definition_version_mismatch() -> None:
    definition = workflow(task("A"))
    runner, store = runtime({"handlers:A": lambda: None})
    run = runner.run(definition)
    different_definition = WorkflowDefinition(
        workflow_id=WorkflowId("workflow"),
        version="2",
        tasks=(task("A"),),
    )

    with pytest.raises(ManifestInvariantError, match="version mismatch"):
        RunManifestBuilder(metadata_store=store).build(
            workflow=different_definition,
            run_id=run.run_id,
        )
