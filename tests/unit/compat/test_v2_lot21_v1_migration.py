"""LOT-21 V1 -> V2 migration contract qualification."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pyworkflowkit._compat.v1_to_v2 import (
    MigrationDisposition,
    TaskAttemptMigrationContext,
    V1MigrationEvidenceError,
    V1MigrationUnsupportedError,
    WorkflowRunMigrationContext,
    export_v1_runtime_metadata,
    import_v1_runtime_metadata,
    migrate_external_run_ref,
    migrate_task_attempt,
    migrate_task_attempt_sequence,
    migrate_task_definition,
    migrate_task_run,
    migrate_workflow_definition,
    migrate_workflow_run,
    migration_contract_snapshot,
)
from pyworkflowkit.authoring import RegisteredWorkload
from pyworkflowkit.diagnostics import FailureCategory
from pyworkflowkit.domain.definitions import (
    TaskDefinition as V1TaskDefinition,
    WorkflowDefinition as V1WorkflowDefinition,
)
from pyworkflowkit.domain.enums import (
    BackoffStrategy,
    TaskAttemptStatus as V1TaskAttemptStatus,
    TaskRunStatus as V1TaskRunStatus,
    TimeoutMode,
    WorkflowRunStatus as V1WorkflowRunStatus,
)
from pyworkflowkit.domain.ids import (
    ExternalRunRefId,
    TaskAttemptId as V1TaskAttemptId,
    TaskId,
    TaskRunId as V1TaskRunId,
    WorkflowId,
    WorkflowRunId as V1WorkflowRunId,
)
from pyworkflowkit.domain.runtime import (
    TaskAttempt as V1TaskAttempt,
    TaskRun as V1TaskRun,
    WorkflowRun as V1WorkflowRun,
)
from pyworkflowkit.domain.values import (
    ExternalRunRef as V1ExternalRunRef,
    RetryPolicy as V1RetryPolicy,
    WorkflowParameter,
)
from pyworkflowkit.runtime import CorrelationContext, CorrelationId
from pyworkflowkit.states import (
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)

T0 = datetime(2026, 10, 3, 8, 0, tzinfo=UTC)
T1 = T0 + timedelta(seconds=1)
T2 = T0 + timedelta(seconds=2)


def _task(
    *,
    handler_ref: str | None = "jobs.customer360",
    executor_key: str = "local",
    timeout_mode: TimeoutMode = TimeoutMode.NONE,
    timeout_seconds: float | None = None,
    retry_categories: frozenset[str] = frozenset(),
) -> V1TaskDefinition:
    return V1TaskDefinition(
        task_id=TaskId("transform"),
        handler_ref=handler_ref,
        depends_on=(TaskId("ingest"),),
        retry_policy=V1RetryPolicy(
            max_attempts=3,
            backoff_strategy=BackoffStrategy.FIXED,
            delay_seconds=2.0,
            max_delay_seconds=8.0,
            retryable_error_categories=retry_categories,
        ),
        executor_key=executor_key,
        timeout_seconds=timeout_seconds,
        timeout_mode=timeout_mode,
        tags=frozenset({"customer360", "migration"}),
        description="legacy transform",
    )


def test_lot21_migrates_explicit_v1_task_to_registry_backed_v2_task() -> None:
    migrated = migrate_task_definition(
        _task(retry_categories=frozenset({"transient"}))
    )

    assert migrated.key == "transform"
    assert migrated.dependencies == ("ingest",)
    assert isinstance(migrated.workload, RegisteredWorkload)
    assert migrated.workload.registry_key == "jobs.customer360"
    assert migrated.workload.executor_key == "inline"
    assert migrated.retry_policy.max_attempts == 3
    assert migrated.retry_policy.initial_delay_seconds == 2.0
    assert migrated.retry_policy.retryable_failure_categories == {
        FailureCategory.TRANSIENT
    }
    assert migrated.timeout_policy.execution_timeout is None
    assert migrated.metadata["migration.legacy_task_id"] == "transform"
    assert migrated.metadata["migration.legacy_executor_key"] == "local"


def test_lot21_workflow_migration_preserves_identity_topology_and_failure_policy() -> None:
    ingest = V1TaskDefinition(
        task_id=TaskId("ingest"),
        handler_ref="jobs.ingest",
    )
    transform = _task()
    workflow = V1WorkflowDefinition(
        workflow_id=WorkflowId("customer360"),
        version="7",
        tasks=(ingest, transform),
        description="legacy customer360",
    )

    migrated = migrate_workflow_definition(workflow)

    assert migrated.name == "customer360"
    assert migrated.version == "7"
    assert tuple(task.key for task in migrated.tasks) == ("ingest", "transform")
    assert migrated.task("transform").dependencies == ("ingest",)
    assert migrated.metadata["migration.source_contract"] == "pyworkflowkit-1.1"


@pytest.mark.parametrize(
    ("task", "code", "disposition"),
    [
        (
            _task(handler_ref=None),
            "PWK-MIG-V1-HANDLER-REF-MISSING",
            MigrationDisposition.INSUFFICIENT_EVIDENCE,
        ),
        (
            _task(
                timeout_mode=TimeoutMode.HARD,
                timeout_seconds=30.0,
            ),
            "PWK-MIG-V1-HARD-TIMEOUT",
            MigrationDisposition.UNSUPPORTED,
        ),
        (
            _task(executor_key="custom-executor"),
            "PWK-MIG-V1-EXECUTOR",
            MigrationDisposition.UNSUPPORTED,
        ),
        (
            _task(retry_categories=frozenset({"legacy-magical-category"})),
            "PWK-MIG-V1-RETRY-CATEGORY",
            MigrationDisposition.UNSUPPORTED,
        ),
    ],
)
def test_lot21_task_migration_fails_closed_for_ambiguous_semantics(
    task: V1TaskDefinition,
    code: str,
    disposition: MigrationDisposition,
) -> None:
    with pytest.raises(
        (V1MigrationEvidenceError, V1MigrationUnsupportedError)
    ) as caught:
        migrate_task_definition(task)

    assert caught.value.issue.code == code
    assert caught.value.issue.disposition is disposition


def test_lot21_workflow_parameters_are_not_silently_reinterpreted() -> None:
    workflow = V1WorkflowDefinition(
        workflow_id=WorkflowId("parameterized"),
        version="1",
        tasks=(
            V1TaskDefinition(
                task_id=TaskId("task"),
                handler_ref="jobs.task",
            ),
        ),
        parameters=(WorkflowParameter(name="region"),),
    )

    with pytest.raises(V1MigrationUnsupportedError) as caught:
        migrate_workflow_definition(workflow)

    assert caught.value.issue.code == "PWK-MIG-V1-WORKFLOW-PARAMETERS"
    assert caught.value.issue.field == "parameters"


def test_lot21_workflow_run_requires_explicit_missing_v2_identity_evidence() -> None:
    legacy = V1WorkflowRun(
        run_id=V1WorkflowRunId("W-42"),
        workflow_id=WorkflowId("customer360"),
        workflow_version="7",
        status=V1WorkflowRunStatus.SUCCEEDED,
        created_at=T0,
        started_at=T1,
        finished_at=T2,
    )
    context = WorkflowRunMigrationContext(
        definition_fingerprint="sha256:def",
        plan_fingerprint="sha256:plan",
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-42"),
            causation_id="legacy-import",
        ),
    )

    migrated = migrate_workflow_run(legacy, context=context)

    assert str(migrated.run_id) == "W-42"
    assert migrated.workflow_name == "customer360"
    assert migrated.status is WorkflowRunStatus.SUCCEEDED
    assert migrated.definition_fingerprint == "sha256:def"
    assert migrated.plan_fingerprint == "sha256:plan"
    assert str(migrated.correlation.correlation_id) == "C-42"


def test_lot21_workflow_run_does_not_invent_missing_created_at() -> None:
    legacy = V1WorkflowRun(
        run_id=V1WorkflowRunId("W-42"),
        workflow_id=WorkflowId("customer360"),
        workflow_version="7",
    )
    context = WorkflowRunMigrationContext(
        definition_fingerprint="sha256:def",
        plan_fingerprint="sha256:plan",
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-42"),
        ),
    )

    with pytest.raises(V1MigrationEvidenceError) as caught:
        migrate_workflow_run(legacy, context=context)

    assert caught.value.issue.field == "created_at"


def test_lot21_task_run_and_attempt_preserve_legacy_identity_and_failure_evidence() -> None:
    legacy_task = V1TaskRun(
        task_run_id=V1TaskRunId("TR-42"),
        run_id=V1WorkflowRunId("W-42"),
        task_id=TaskId("transform"),
        status=V1TaskRunStatus.FAILED,
        created_at=T0,
        started_at=T1,
        finished_at=T2,
    )
    legacy_attempt = V1TaskAttempt(
        attempt_id=V1TaskAttemptId("TA-42"),
        task_run_id=V1TaskRunId("TR-42"),
        attempt_number=2,
        status=V1TaskAttemptStatus.FAILED,
        started_at=T1,
        finished_at=T2,
        error_type="LegacyProviderError",
        error_message="legacy provider failed",
        error_category="provider",
        retry_eligible_at=T2,
        error_metadata={"provider_code": 503},
    )

    migrated_task = migrate_task_run(legacy_task)
    migrated_attempt = migrate_task_attempt(
        legacy_attempt,
        context=TaskAttemptMigrationContext(created_at=T0),
    )

    assert str(migrated_task.task_run_id) == "TR-42"
    assert migrated_task.status is TaskRunStatus.FAILED
    assert str(migrated_attempt.attempt.attempt_id) == "TA-42"
    assert migrated_attempt.attempt.attempt_number == 2
    assert migrated_attempt.attempt.status is TaskAttemptStatus.FAILED
    assert migrated_attempt.attempt.failure is None
    assert migrated_attempt.legacy_evidence.retry_eligible_at == T2
    assert migrated_attempt.legacy_evidence.error_type == "LegacyProviderError"
    assert migrated_attempt.legacy_evidence.error_category == "provider"
    assert migrated_attempt.legacy_evidence.error_metadata["provider_code"] == 503


def test_lot21_retry_history_migrates_as_contiguous_attempt_sequence() -> None:
    attempts = (
        V1TaskAttempt(
            attempt_id=V1TaskAttemptId("TA-1"),
            task_run_id=V1TaskRunId("TR-42"),
            attempt_number=1,
            status=V1TaskAttemptStatus.FAILED,
            started_at=T0,
            finished_at=T1,
            error_type="Transient",
        ),
        V1TaskAttempt(
            attempt_id=V1TaskAttemptId("TA-2"),
            task_run_id=V1TaskRunId("TR-42"),
            attempt_number=2,
            status=V1TaskAttemptStatus.SUCCEEDED,
            started_at=T1,
            finished_at=T2,
        ),
    )

    migrated = migrate_task_attempt_sequence(
        attempts,
        created_at_by_attempt_id={"TA-1": T0, "TA-2": T1},
    )

    assert tuple(item.attempt.attempt_number for item in migrated) == (1, 2)
    assert tuple(str(item.attempt.attempt_id) for item in migrated) == ("TA-1", "TA-2")
    assert migrated[0].legacy_evidence.error_type == "Transient"


def test_lot21_retry_history_rejects_gaps_and_missing_creation_evidence() -> None:
    gap = (
        V1TaskAttempt(
            attempt_id=V1TaskAttemptId("TA-2"),
            task_run_id=V1TaskRunId("TR-42"),
            attempt_number=2,
            status=V1TaskAttemptStatus.SUCCEEDED,
            started_at=T1,
            finished_at=T2,
        ),
    )
    with pytest.raises(V1MigrationUnsupportedError) as caught:
        migrate_task_attempt_sequence(
            gap,
            created_at_by_attempt_id={"TA-2": T1},
        )
    assert caught.value.issue.code == "PWK-MIG-V1-ATTEMPT-SEQUENCE"

    first = V1TaskAttempt(
        attempt_id=V1TaskAttemptId("TA-1"),
        task_run_id=V1TaskRunId("TR-42"),
        attempt_number=1,
        status=V1TaskAttemptStatus.SUCCEEDED,
        started_at=T1,
        finished_at=T2,
    )
    with pytest.raises(V1MigrationEvidenceError):
        migrate_task_attempt_sequence(
            (first,),
            created_at_by_attempt_id={},
        )


def test_lot21_external_tracking_requires_explicit_kind_and_preserves_legacy_fields() -> None:
    legacy = V1ExternalRunRef(
        external_ref_id=ExternalRunRefId("ER-42"),
        provider="legacy-provider",
        external_run_id="REMOTE-42",
        uri="https://legacy.invalid/runs/REMOTE-42",
        metadata={"region": "eu-west"},
    )

    migrated = migrate_external_run_ref(
        legacy,
        kind="legacy_job",
        correlation_id=CorrelationId.parse("C-42"),
        causation_id="migration",
    )

    assert migrated.external_run.provider == "legacy-provider"
    assert migrated.external_run.external_run_id == "REMOTE-42"
    assert migrated.external_run.kind == "legacy_job"
    assert dict(migrated.external_run.metadata) == {"region": "eu-west"}
    assert migrated.legacy_evidence.external_ref_id == "ER-42"
    assert migrated.legacy_evidence.uri == "https://legacy.invalid/runs/REMOTE-42"


def test_lot21_external_tracking_rejects_nonportable_metadata() -> None:
    legacy = V1ExternalRunRef(
        external_ref_id=ExternalRunRefId("ER-42"),
        provider="legacy-provider",
        external_run_id="REMOTE-42",
        metadata={"attempts": 3},
    )

    with pytest.raises(V1MigrationUnsupportedError) as caught:
        migrate_external_run_ref(legacy, kind="legacy_job")

    assert caught.value.issue.code == "PWK-MIG-V1-EXTERNAL-METADATA"



def test_lot21_runtime_metadata_semantic_export_import_roundtrip_preserves_known_facts() -> None:
    workflow = V1WorkflowRun(
        run_id=V1WorkflowRunId("W-EXPORT"),
        workflow_id=WorkflowId("customer360"),
        workflow_version="7",
        status=V1WorkflowRunStatus.FAILED,
        parameters={"region": "eu", "limit": 10},
        created_at=T0,
        started_at=T1,
        finished_at=T2,
    )
    task_run = V1TaskRun(
        task_run_id=V1TaskRunId("TR-EXPORT"),
        run_id=workflow.run_id,
        task_id=TaskId("publish"),
        status=V1TaskRunStatus.FAILED,
        created_at=T0,
        started_at=T1,
        finished_at=T2,
    )
    attempt = V1TaskAttempt(
        attempt_id=V1TaskAttemptId("TA-EXPORT"),
        task_run_id=task_run.task_run_id,
        attempt_number=2,
        status=V1TaskAttemptStatus.FAILED,
        started_at=T1,
        finished_at=T2,
        error_type="LegacyError",
        error_message="publish failed",
        error_category="provider",
        retry_eligible_at=T2,
        error_metadata={"provider_code": 503, "retryable": True},
    )
    external = V1ExternalRunRef(
        external_ref_id=ExternalRunRefId("ER-EXPORT"),
        provider="legacy-provider",
        external_run_id="REMOTE-EXPORT",
        uri="https://legacy.invalid/runs/REMOTE-EXPORT",
        metadata={"region": "eu"},
    )

    exported = export_v1_runtime_metadata(
        workflow_run=workflow,
        task_runs=(task_run,),
        task_attempts=(attempt,),
        external_runs=(external,),
    )
    payload = exported.to_json()
    restored = import_v1_runtime_metadata(payload)

    assert restored.to_json() == payload
    assert restored.workflow_run.parameters == {"region": "eu", "limit": 10}
    assert restored.task_attempts[0].retry_eligible_at == T2
    assert restored.task_attempts[0].error_metadata["provider_code"] == 503
    assert restored.external_runs[0].uri == external.uri
    assert restored.to_payload()["external_run_attempt_ownership"] is None


def test_lot21_runtime_metadata_import_rejects_invented_external_attempt_ownership() -> None:
    workflow = V1WorkflowRun(
        run_id=V1WorkflowRunId("W-EXPORT"),
        workflow_id=WorkflowId("customer360"),
        workflow_version="7",
        status=V1WorkflowRunStatus.PENDING,
        created_at=T0,
    )
    exported = export_v1_runtime_metadata(
        workflow_run=workflow,
        task_runs=(),
        task_attempts=(),
    )
    payload = exported.to_payload()
    payload["external_run_attempt_ownership"] = {"ER-42": "TA-42"}

    import json

    with pytest.raises(ValueError, match="must not invent ExternalRunRef TaskAttempt ownership"):
        import_v1_runtime_metadata(
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )

def test_lot21_snapshot_freezes_no_invention_migration_posture() -> None:
    snapshot = migration_contract_snapshot()

    assert snapshot["direction"] == "v1_to_v2_only"
    assert snapshot["generic_aliases_preserved"] is False
    assert snapshot["default_executor_mapping"] == {"local": "inline"}
    assert snapshot["hard_timeout_automatic_mapping"] is False
    assert snapshot["workflow_run_requires_external_fingerprints"] is True
    assert snapshot["workflow_run_requires_external_correlation"] is True
    assert snapshot["task_attempt_requires_external_created_at"] is True
    assert snapshot["retry_history_requires_contiguous_attempt_numbers"] is True
    assert snapshot["external_run_kind_requires_explicit_input"] is True
    assert snapshot["semantic_metadata_export_import"] is True
    assert snapshot["semantic_metadata_external_attempt_ownership"] is None
    assert snapshot["ambiguous_external_attempt_ownership_invented"] is False
