"""Stable machine-facing CLI contract introduced by M43."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

CLI_MACHINE_CONTRACT_VERSION = "1"

CLI_COMMANDS: tuple[str, ...] = (
    "doctor",
    "events",
    "inspect",
    "manifest",
    "plan",
    "plugins",
    "run",
    "validate",
    "version",
)

CLI_JSON_COMMANDS: frozenset[str] = frozenset(
    {
        "doctor",
        "events",
        "inspect",
        "manifest",
        "plan",
        "plugins",
        "run",
        "validate",
    }
)

CLI_EXIT_CODES: Mapping[str, int] = MappingProxyType(
    {
        "success": 0,
        "validation": 2,
        "run_failure": 3,
        "doctor_failure": 4,
    }
)

CLI_ERROR_REQUIRED_KEYS: frozenset[str] = frozenset({"error", "exit_code"})

CLI_JSON_REQUIRED_KEYS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "validate": frozenset(
            {
                "valid",
                "workflow_id",
                "workflow_version",
                "task_count",
            }
        ),
        "plan": frozenset(
            {
                "workflow_id",
                "workflow_version",
                "groups",
            }
        ),
        "run": frozenset(
            {
                "run_id",
                "workflow_id",
                "workflow_version",
                "status",
                "created_at",
                "started_at",
                "finished_at",
            }
        ),
        "inspect": frozenset(
            {
                "run_id",
                "workflow_id",
                "workflow_version",
                "status",
                "created_at",
                "started_at",
                "finished_at",
            }
        ),
        "events": frozenset({"run_id", "events"}),
        "plugins": frozenset({"count", "plugins"}),
        "doctor": frozenset({"healthy", "plugin_api_version", "plugins"}),
        "manifest": frozenset(
            {
                "schema_version",
                "run_id",
                "workflow_id",
                "workflow_version",
                "status",
                "parameters",
                "created_at",
                "started_at",
                "finished_at",
                "tasks",
                "events",
            }
        ),
    }
)

CLI_JSON_NESTED_REQUIRED_KEYS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "plan.groups[]": frozenset({"index", "tasks"}),
        "events.events[]": frozenset(
            {
                "event_id",
                "event_sequence",
                "event_type",
                "occurred_at",
                "task_run_id",
                "task_id",
                "attempt_number",
                "payload",
            }
        ),
        "plugins.plugins[]": frozenset(
            {
                "name",
                "type",
                "group",
                "value",
                "distribution",
                "status",
            }
        ),
        "doctor.plugins[]": frozenset({"name", "type", "status", "error"}),
        "manifest.tasks[]": frozenset(
            {
                "task_run_id",
                "task_id",
                "status",
                "skip_reason",
                "created_at",
                "started_at",
                "finished_at",
                "attempts",
                "artifacts",
                "external_refs",
            }
        ),
        "manifest.tasks[].attempts[]": frozenset(
            {
                "attempt_id",
                "attempt_number",
                "status",
                "started_at",
                "finished_at",
                "error_type",
                "error_category",
            }
        ),
        "manifest.tasks[].artifacts[]": frozenset(
            {
                "artifact_id",
                "name",
                "uri",
                "media_type",
                "checksum",
                "size_bytes",
                "metadata",
            }
        ),
        "manifest.tasks[].external_refs[]": frozenset(
            {
                "external_ref_id",
                "provider",
                "external_run_id",
                "uri",
                "metadata",
            }
        ),
        "manifest.events[]": frozenset(
            {
                "event_id",
                "event_sequence",
                "event_type",
                "occurred_at",
                "task_run_id",
                "task_id",
                "attempt_number",
                "payload",
            }
        ),
    }
)

__all__ = [
    "CLI_COMMANDS",
    "CLI_ERROR_REQUIRED_KEYS",
    "CLI_EXIT_CODES",
    "CLI_JSON_COMMANDS",
    "CLI_JSON_NESTED_REQUIRED_KEYS",
    "CLI_JSON_REQUIRED_KEYS",
    "CLI_MACHINE_CONTRACT_VERSION",
]
