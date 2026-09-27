"""M41 compatibility-contract reference acceptance."""

from __future__ import annotations

from importlib.resources import files

import pyworkflowkit
from pyworkflowkit.application.manifest import MANIFEST_SCHEMA_VERSION
from pyworkflowkit.cli import (
    DOCTOR_FAILURE_EXIT,
    RUN_FAILURE_EXIT,
    VALIDATION_EXIT,
    app,
)
from pyworkflowkit.domain.enums import (
    RuntimeEventType,
    TaskAttemptStatus,
    TaskRunStatus,
    WorkflowRunStatus,
)
from pyworkflowkit.plugins import PLUGIN_API_VERSION
from pyworkflowkit.ports.metadata_store import MetadataStore, UnitOfWork

EXPECTED_PUBLIC_API = {
    "ArtifactId",
    "ArtifactReference",
    "BackoffStrategy",
    "ExternalRunRef",
    "ExternalRunRefId",
    "FailurePolicy",
    "PyWorkflowKitError",
    "RetryPolicy",
    "RunContext",
    "RuntimeSettings",
    "TaskDefinition",
    "TaskHandle",
    "TaskId",
    "TaskResult",
    "TimeoutMode",
    "WorkflowBuilder",
    "WorkflowDefinition",
    "WorkflowId",
    "WorkflowParameter",
    "WorkflowRuntime",
    "__version__",
    "task",
    "workflow",
}

EXPECTED_METADATA_STORE_METHODS = {
    "get_task_output_checkpoint",
    "get_task_run",
    "get_workflow_run",
    "list_artifacts",
    "list_events",
    "list_external_run_refs",
    "list_task_attempts",
    "list_task_runs",
    "list_workflow_runs",
    "unit_of_work",
}

EXPECTED_UNIT_OF_WORK_METHODS = {
    "__enter__",
    "__exit__",
    "add_artifact",
    "add_event",
    "add_external_run_ref",
    "add_task_attempt",
    "add_task_output_checkpoint",
    "add_task_run",
    "add_workflow_run",
    "commit",
    "rollback",
    "save_task_attempt",
    "save_task_run",
    "save_workflow_run",
}

EXPECTED_CLI_COMMANDS = {
    "doctor",
    "events",
    "inspect",
    "manifest",
    "plan",
    "plugins",
    "run",
    "validate",
    "version",
}


def _protocol_methods(protocol: type[object]) -> set[str]:
    return {
        name
        for name, value in protocol.__dict__.items()
        if callable(value) and (not name.startswith("_") or name in {"__enter__", "__exit__"})
    }


def _registered_cli_commands() -> set[str]:
    names: set[str] = set()
    for command in app.registered_commands:
        if command.name is not None:
            names.add(command.name)
            continue
        callback = command.callback
        assert callback is not None
        names.add(callback.__name__.replace("_", "-"))
    return names


def test_m41_package_root_api_baseline_is_explicit() -> None:
    assert set(pyworkflowkit.__all__) == EXPECTED_PUBLIC_API


def test_m41_runtime_vocabulary_baseline_is_explicit() -> None:
    assert tuple(item.value for item in WorkflowRunStatus) == (
        "PENDING",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    )
    assert tuple(item.value for item in TaskRunStatus) == (
        "PENDING",
        "READY",
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "SKIPPED",
        "CANCELLED",
    )
    assert tuple(item.value for item in TaskAttemptStatus) == (
        "RUNNING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    )
    assert tuple(item.value for item in RuntimeEventType) == (
        "WORKFLOW_STARTED",
        "WORKFLOW_SUCCEEDED",
        "WORKFLOW_FAILED",
        "WORKFLOW_CANCELLED",
        "TASK_READY",
        "TASK_STARTED",
        "TASK_RETRYING",
        "TASK_SUCCEEDED",
        "TASK_FAILED",
        "TASK_SKIPPED",
    )


def test_m41_persistence_port_baseline_is_explicit() -> None:
    assert _protocol_methods(MetadataStore) == EXPECTED_METADATA_STORE_METHODS
    assert _protocol_methods(UnitOfWork) == EXPECTED_UNIT_OF_WORK_METHODS


def test_m41_cli_surface_and_exit_codes_are_explicit() -> None:
    assert _registered_cli_commands() == EXPECTED_CLI_COMMANDS
    assert VALIDATION_EXIT == 2
    assert RUN_FAILURE_EXIT == 3
    assert DOCTOR_FAILURE_EXIT == 4


def test_m41_versioned_portable_contracts_remain_v1() -> None:
    assert MANIFEST_SCHEMA_VERSION == "1"
    assert PLUGIN_API_VERSION == "1"


def test_m41_migration_history_is_packaged_through_0_6_head() -> None:
    versions = files("pyworkflowkit.migrations.versions")
    assert versions.joinpath("0001_runtime_metadata.py").is_file()
    assert versions.joinpath("0002_task_output_checkpoints.py").is_file()
    assert versions.joinpath("0003_retry_eligible_at.py").is_file()
