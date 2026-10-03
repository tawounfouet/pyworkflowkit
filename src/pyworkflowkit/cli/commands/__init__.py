"""CLI commands package."""

from __future__ import annotations

from pyworkflowkit.cli.commands.doctor import doctor_command
from pyworkflowkit.cli.commands.legacy import (
    RUN_FAILURE_EXIT,
    VALIDATION_EXIT,
    events_command,
    inspect_command,
    manifest_command,
    plan_command,
    plugins_command,
    run_command,
    validate_command,
)
from pyworkflowkit.cli.commands.version import version_command

__all__ = [
    "RUN_FAILURE_EXIT",
    "VALIDATION_EXIT",
    "doctor_command",
    "events_command",
    "inspect_command",
    "manifest_command",
    "plan_command",
    "plugins_command",
    "run_command",
    "validate_command",
    "version_command",
]
