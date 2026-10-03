"""M51 reference acceptance for the public control-plane provider boundary."""

from __future__ import annotations

import json

import pytest

from pyworkflowkit._compat.v1_root import WorkflowRuntime
from pyworkflowkit.control_plane import (
    CONTROL_PLANE_PROVIDER_CONTRACT_VERSION,
    ControlPlaneCapabilityError,
    ControlPlaneProvider,
    WorkflowRuntimeProvider,
)


def _workflow_payload() -> dict[str, object]:
    return {
        "workflow_id": "reference.control-plane",
        "version": "1",
        "tasks": [
            {
                "task_id": "fetch",
                "handler_ref": "reference.fetch",
            },
            {
                "task_id": "publish",
                "handler_ref": "reference.publish",
                "depends_on": ["fetch"],
            },
        ],
        "parameters": [
            {
                "name": "api_token",
                "required": False,
                "default": None,
                "sensitive": True,
            }
        ],
        "description": "M51 provider acceptance workflow",
    }


def test_control_plane_provider_operates_runtime_through_portable_contracts() -> None:
    runtime = WorkflowRuntime()
    runtime.register("reference.fetch", lambda: {"rows": 3})
    runtime.register("reference.publish", lambda: "published")
    provider = WorkflowRuntimeProvider(runtime)

    assert isinstance(provider, ControlPlaneProvider)
    assert CONTROL_PLANE_PROVIDER_CONTRACT_VERSION == "1"

    capabilities = provider.inspect_capabilities()
    assert capabilities.operations["execute_workflow"] is True
    assert capabilities.operations["request_cancellation"] is False
    assert capabilities.scheduling_owned_by_control_plane is True
    assert capabilities.background_execution is False

    workflow = _workflow_payload()
    validation = provider.validate_workflow(workflow)
    assert validation.valid is True
    assert validation.workflow_id == "reference.control-plane"
    assert validation.task_count == 2

    inspection = provider.inspect_workflow(workflow)
    assert inspection.task_order == ("fetch", "publish")
    assert tuple(group.task_ids for group in inspection.groups) == (("fetch",), ("publish",))

    run = provider.execute_workflow(
        workflow,
        parameters={"api_token": "do-not-return"},
    )
    assert run.status == "SUCCEEDED"
    assert "parameters" not in run.model_dump()

    inspected = provider.inspect_run(run.run_id)
    assert inspected == run

    events = provider.list_runtime_events(run.run_id)
    assert events
    assert tuple(event.event_sequence for event in events) == tuple(
        sorted(event.event_sequence for event in events)
    )

    manifest = provider.retrieve_manifest(workflow, run.run_id)
    assert manifest["schema_version"] == "1"
    assert manifest["run_id"] == run.run_id
    assert manifest["parameters"]["api_token"] == "<redacted>"

    lineage = provider.retrieve_lineage(workflow, run.run_id)
    assert lineage.run_id == run.run_id
    assert tuple(task.task_id for task in lineage.tasks) == ("fetch", "publish")
    assert len(lineage.dependencies) == 1

    recovery = provider.assess_recovery(run.run_id)
    assert recovery.workflow_status == "SUCCEEDED"
    assert recovery.liveness == "terminal"
    assert recovery.resume_eligibility == "not_eligible"

    with pytest.raises(ControlPlaneCapabilityError):
        provider.request_cancellation(run.run_id, reason="reference test")

    portable = {
        "capabilities": capabilities.model_dump(mode="json"),
        "validation": validation.model_dump(mode="json"),
        "inspection": inspection.model_dump(mode="json"),
        "run": run.model_dump(mode="json"),
        "events": [event.model_dump(mode="json") for event in events],
        "manifest": manifest,
        "lineage": lineage.model_dump(mode="json"),
        "recovery": recovery.model_dump(mode="json"),
    }
    json.dumps(portable, allow_nan=False, sort_keys=True)
