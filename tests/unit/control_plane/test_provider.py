"""M51 unit coverage for the control-plane provider contract."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from pyworkflowkit.application.runtime import WorkflowRuntime
from pyworkflowkit.control_plane import (
    CONTROL_PLANE_OPERATIONS,
    CONTROL_PLANE_PROVIDER_CONTRACT_VERSION,
    ControlPlaneCapabilityError,
    ControlPlaneOperation,
    ControlPlaneProvider,
    WorkflowRuntimeProvider,
)
from pyworkflowkit.domain.enums import RuntimeEventType
from pyworkflowkit.domain.ids import RuntimeEventId, WorkflowRunId
from pyworkflowkit.domain.runtime import RuntimeEvent
from pyworkflowkit.errors import SerializationError


def test_control_plane_contract_version_and_operation_inventory_are_stable() -> None:
    assert CONTROL_PLANE_PROVIDER_CONTRACT_VERSION == "1"
    assert CONTROL_PLANE_OPERATIONS == (
        "validate_workflow",
        "inspect_workflow",
        "execute_workflow",
        "inspect_run",
        "list_runtime_events",
        "retrieve_manifest",
        "retrieve_lineage",
        "request_cancellation",
        "assess_recovery",
        "reconcile_run",
        "resume_run",
        "inspect_capabilities",
    )


def test_workflow_runtime_provider_satisfies_public_protocol() -> None:
    provider = WorkflowRuntimeProvider(WorkflowRuntime())

    assert isinstance(provider, ControlPlaneProvider)


def test_capabilities_report_external_ownership_and_unsupported_cancellation() -> None:
    provider = WorkflowRuntimeProvider(WorkflowRuntime())
    capabilities = provider.inspect_capabilities()

    assert capabilities.contract_version == "1"
    assert capabilities.provider_name == "pyworkflowkit.local"
    assert set(capabilities.operations) == set(CONTROL_PLANE_OPERATIONS)
    assert capabilities.operations[ControlPlaneOperation.REQUEST_CANCELLATION.value] is False
    assert all(
        enabled
        for operation, enabled in capabilities.operations.items()
        if operation != ControlPlaneOperation.REQUEST_CANCELLATION.value
    )
    assert capabilities.scheduling_owned_by_control_plane is True
    assert capabilities.background_execution is False


def test_validate_workflow_returns_portable_diagnostics_instead_of_private_objects() -> None:
    provider = WorkflowRuntimeProvider(WorkflowRuntime())
    invalid = {
        "workflow_id": "reference.invalid",
        "version": "1",
        "tasks": [
            {
                "task_id": "loop",
                "handler_ref": "reference.loop",
                "depends_on": ["loop"],
            }
        ],
    }

    result = provider.validate_workflow(invalid)

    assert result.valid is False
    assert result.workflow_id == "reference.invalid"
    assert result.task_count == 1
    assert result.diagnostics
    assert "cannot depend on itself" in result.diagnostics[0]


class _EventOnlyRuntime:
    def events(self, run_id: str) -> tuple[RuntimeEvent, ...]:
        assert run_id == "run-1"
        return (
            RuntimeEvent(
                event_id=RuntimeEventId("event-1"),
                event_type=RuntimeEventType.TASK_STARTED,
                run_id=WorkflowRunId("run-1"),
                occurred_at=datetime.now(UTC),
                event_sequence=1,
                payload={
                    "authorization": "Bearer secret",
                    "nested": {"api_token": "hidden", "safe": "visible"},
                },
            ),
        )


def test_control_plane_event_projection_defensively_redacts_sensitive_payload() -> None:
    provider = WorkflowRuntimeProvider(cast(WorkflowRuntime, _EventOnlyRuntime()))

    events = provider.list_runtime_events("run-1")

    assert events[0].payload == {
        "authorization": "<redacted>",
        "nested": {"api_token": "<redacted>", "safe": "visible"},
    }


def test_unsupported_cancellation_is_explicit_and_matches_capabilities() -> None:
    provider = WorkflowRuntimeProvider(WorkflowRuntime())

    with pytest.raises(ControlPlaneCapabilityError) as caught:
        provider.request_cancellation("run-1", reason="operator request")

    assert caught.value.operation == "request_cancellation"


def test_non_portable_parameters_are_rejected_before_runtime_execution() -> None:
    runtime = WorkflowRuntime()
    runtime.register("reference.work", lambda: "ok")
    provider = WorkflowRuntimeProvider(runtime)
    workflow = {
        "workflow_id": "reference.parameters",
        "version": "1",
        "tasks": [{"task_id": "work", "handler_ref": "reference.work"}],
    }

    with pytest.raises(SerializationError) as caught:
        provider.execute_workflow(workflow, parameters={"bad": object()})

    assert "portable JSON" in str(caught.value)
