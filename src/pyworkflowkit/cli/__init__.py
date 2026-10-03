"""Local operational CLI for PyWorkflowKit."""

from __future__ import annotations

from pyworkflowkit.cli.app import app
from pyworkflowkit.cli.bootstrap import load_workflow_from_spec, main
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
from pyworkflowkit.cli.context import CliContext, OutputMode
from pyworkflowkit.cli.exit_codes import ExitCode
from pyworkflowkit.cli.security import (
    REDACTED,
    SecurityError,
    assert_path_within_workspace,
    redact_text,
    redacted_traceback,
    sanitize_input_path,
)
from pyworkflowkit.cli.services.doctor_service import DoctorService
from pyworkflowkit.config import RuntimeSettings
from pyworkflowkit.declarative import WorkflowBuilder
from pyworkflowkit.domain.definitions import WorkflowDefinition
from pyworkflowkit.plugins import PluginCatalog, PluginDiscovery

DOCTOR_FAILURE_EXIT = int(ExitCode.DOCTOR_FAILURE)

__all__ = [
    "DOCTOR_FAILURE_EXIT",
    "REDACTED",
    "RUN_FAILURE_EXIT",
    "VALIDATION_EXIT",
    "CliContext",
    "DoctorService",
    "ExitCode",
    "OutputMode",
    "PluginCatalog",
    "PluginDiscovery",
    "RuntimeSettings",
    "SecurityError",
    "WorkflowBuilder",
    "WorkflowDefinition",
    "app",
    "assert_path_within_workspace",
    "doctor_command",
    "events_command",
    "inspect_command",
    "load_workflow_from_spec",
    "main",
    "manifest_command",
    "plan_command",
    "plugins_command",
    "redact_text",
    "redacted_traceback",
    "run_command",
    "sanitize_input_path",
    "validate_command",
    "version_command",
]
