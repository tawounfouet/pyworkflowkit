"""Coverage margin for LOT-12 validation and fail-closed evidence contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

import pytest

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.diagnostics import RuntimeInspector
from pyworkflowkit.errors import RuntimeInvariantError
from pyworkflowkit.lineage import ExecutionLineageProjector, RunManifestBuilder
from pyworkflowkit.persistence import InMemoryMetadataStore
from pyworkflowkit.planning import WorkflowPlanner
from pyworkflowkit.runtime import (
    CorrelationContext,
    CorrelationId,
    RuntimeEvent,
    RuntimeEventType,
    TaskAttemptId,
    TaskOutputCheckpoint,
    TaskRunId,
    WorkflowRun,
    WorkflowRunId,
)
from pyworkflowkit.runtime.evidence import normalize_json_value, plain_json_value

NOW = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)


class ExampleEnum(StrEnum):
    VALUE = "value"


def _event(**changes: object) -> RuntimeEvent:
    values: dict[str, object] = {
        "sequence": 1,
        "event_type": RuntimeEventType.WORKFLOW_STATE_CHANGED,
        "workflow_run_id": WorkflowRunId.parse("W-1"),
        "occurred_at": NOW,
        "from_status": "PENDING",
        "to_status": "RUNNING",
        "payload": {"nested": [1, True, ExampleEnum.VALUE]},
    }
    values.update(changes)
    return RuntimeEvent(**values)  # type: ignore[arg-type]


def _workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="lot12-coverage",
        tasks=(TaskDefinition(key="task", workload=lambda: {"ok": True}),),
    )


def _run_for_plan(
    store: InMemoryMetadataStore,
    *,
    definition_fingerprint: str,
    plan_fingerprint: str,
) -> WorkflowRun:
    run = WorkflowRun(
        run_id=WorkflowRunId.parse("W-COVERAGE"),
        workflow_name="lot12-coverage",
        workflow_version="1",
        definition_fingerprint=definition_fingerprint,
        plan_fingerprint=plan_fingerprint,
        correlation=CorrelationContext(
            correlation_id=CorrelationId.parse("C-COVERAGE"),
        ),
        created_at=NOW,
    )
    store.create_workflow_run(run)
    return run


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_json_normalization_rejects_nonfinite_numbers(value: float) -> None:
    with pytest.raises(ValueError, match="finite JSON"):
        normalize_json_value(value)


def test_json_normalization_handles_enum_sequences_and_plain_conversion() -> None:
    normalized = normalize_json_value(
        {
            "enum": ExampleEnum.VALUE,
            "items": [1, "two", False],
            "nested": {"value": 3},
        }
    )

    assert plain_json_value(normalized) == {
        "enum": "value",
        "items": [1, "two", False],
        "nested": {"value": 3},
    }


def test_json_normalization_rejects_non_string_mapping_keys() -> None:
    with pytest.raises(TypeError, match="mapping keys must be strings"):
        normalize_json_value({1: "invalid"})


def test_json_normalization_rejects_opaque_objects() -> None:
    with pytest.raises(TypeError, match="unsupported value type"):
        normalize_json_value(object())


@pytest.mark.parametrize("sequence", [True, "1"])
def test_runtime_event_requires_integer_sequence(sequence: object) -> None:
    with pytest.raises(TypeError, match="sequence must be an integer"):
        _event(sequence=sequence)


def test_runtime_event_requires_positive_sequence() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        _event(sequence=0)


def test_runtime_event_requires_typed_event_and_workflow_identity() -> None:
    with pytest.raises(TypeError, match="RuntimeEventType"):
        _event(event_type="WORKFLOW_STATE_CHANGED")
    with pytest.raises(TypeError, match="WorkflowRunId"):
        _event(workflow_run_id="W-1")


def test_runtime_event_requires_typed_optional_task_and_attempt_identity() -> None:
    with pytest.raises(TypeError, match="task_run_id"):
        _event(task_run_id="TR-1")
    with pytest.raises(TypeError, match="attempt_id"):
        _event(attempt_id="TA-1")


def test_runtime_event_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _event(occurred_at=datetime(2026, 10, 3, 9, 0))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("from_status", "", "from_status"),
        ("from_status", "   ", "from_status"),
        ("to_status", "", "to_status"),
        ("to_status", "   ", "to_status"),
    ],
)
def test_runtime_event_rejects_blank_statuses(
    field: str,
    value: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _event(**{field: value})


def test_runtime_event_normalizes_payload_immutably() -> None:
    event = _event(
        task_run_id=TaskRunId.parse("TR-1"),
        attempt_id=TaskAttemptId.parse("TA-1"),
    )

    assert plain_json_value(event.payload) == {
        "nested": [1, True, "value"],
    }


def test_output_checkpoint_validates_identity_timestamp_and_digest() -> None:
    with pytest.raises(TypeError, match="TaskRunId"):
        TaskOutputCheckpoint(
            task_run_id="TR-1",  # type: ignore[arg-type]
            output={"rows": 1},
            recorded_at=NOW,
        )

    with pytest.raises(ValueError, match="timezone-aware"):
        TaskOutputCheckpoint(
            task_run_id=TaskRunId.parse("TR-1"),
            output={"rows": 1},
            recorded_at=datetime(2026, 10, 3, 9, 0),
        )

    with pytest.raises(ValueError, match="digest"):
        TaskOutputCheckpoint(
            task_run_id=TaskRunId.parse("TR-1"),
            output={"rows": 1},
            recorded_at=NOW,
            digest="sha256:wrong",
        )


def test_manifest_builder_rejects_invalid_store_and_terminal_requirement() -> None:
    with pytest.raises(TypeError, match="MetadataStore"):
        RunManifestBuilder(metadata=object())  # type: ignore[arg-type]

    store = InMemoryMetadataStore()
    workflow = _workflow()
    plan = WorkflowPlanner().compile(workflow)
    run = _run_for_plan(
        store,
        definition_fingerprint=plan.definition_fingerprint,
        plan_fingerprint=plan.fingerprint(),
    )

    with pytest.raises(RuntimeInvariantError, match="non-terminal"):
        RunManifestBuilder(metadata=store).build(run.run_id, require_terminal=True)


def test_lineage_projector_fails_closed_on_invalid_inputs_and_mismatched_run() -> None:
    with pytest.raises(TypeError, match="MetadataStore"):
        ExecutionLineageProjector(metadata=object())  # type: ignore[arg-type]

    store = InMemoryMetadataStore()
    projector = ExecutionLineageProjector(metadata=store)
    with pytest.raises(TypeError, match="WorkflowDefinition or ExecutionPlan"):
        projector.project(object(), WorkflowRunId.parse("W-MISSING"))  # type: ignore[arg-type]

    workflow = _workflow()
    plan = WorkflowPlanner().compile(workflow)
    run = _run_for_plan(
        store,
        definition_fingerprint="sha256:not-the-plan-definition",
        plan_fingerprint=plan.fingerprint(),
    )

    with pytest.raises(RuntimeInvariantError, match="does not match"):
        projector.project(plan, run.run_id)


def test_lineage_projector_rejects_missing_persisted_task_set() -> None:
    store = InMemoryMetadataStore()
    workflow = _workflow()
    plan = WorkflowPlanner().compile(workflow)
    run = _run_for_plan(
        store,
        definition_fingerprint=plan.definition_fingerprint,
        plan_fingerprint=plan.fingerprint(),
    )

    with pytest.raises(RuntimeInvariantError, match="task set"):
        ExecutionLineageProjector(metadata=store).project(plan, run.run_id)


def test_runtime_inspector_fails_closed_on_invalid_inputs_and_missing_tasks() -> None:
    with pytest.raises(TypeError, match="MetadataStore"):
        RuntimeInspector(metadata=object())  # type: ignore[arg-type]

    store = InMemoryMetadataStore()
    inspector = RuntimeInspector(metadata=store)
    with pytest.raises(TypeError, match="WorkflowDefinition or ExecutionPlan"):
        inspector.inspect(object(), WorkflowRunId.parse("W-MISSING"))  # type: ignore[arg-type]

    workflow = _workflow()
    plan = WorkflowPlanner().compile(workflow)
    run = _run_for_plan(
        store,
        definition_fingerprint=plan.definition_fingerprint,
        plan_fingerprint=plan.fingerprint(),
    )

    with pytest.raises(RuntimeInvariantError, match="missing TaskRun"):
        inspector.inspect(plan, run.run_id)


def test_runtime_inspector_rejects_plan_identity_mismatch() -> None:
    store = InMemoryMetadataStore()
    workflow = _workflow()
    plan = WorkflowPlanner().compile(workflow)
    run = _run_for_plan(
        store,
        definition_fingerprint="sha256:wrong",
        plan_fingerprint=plan.fingerprint(),
    )

    with pytest.raises(RuntimeInvariantError, match="does not match"):
        RuntimeInspector(metadata=store).inspect(plan, run.run_id)
