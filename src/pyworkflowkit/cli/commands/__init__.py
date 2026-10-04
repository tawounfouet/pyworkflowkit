"""CLI commands package for PyWorkflowKit."""

from pyworkflowkit.cli.commands.doctor import doctor_command
from pyworkflowkit.cli.commands.inspect import inspect_command
from pyworkflowkit.cli.commands.legacy import (
    events_command,
    manifest_command,
    plugins_command,
)
from pyworkflowkit.cli.commands.plan import plan_command
from pyworkflowkit.cli.commands.prune import prune_command
from pyworkflowkit.cli.commands.run import run_command
from pyworkflowkit.cli.commands.validate import validate_command
from pyworkflowkit.cli.commands.version import version_command

__all__ = [
    "doctor_command",
    "events_command",
    "inspect_command",
    "manifest_command",
    "plan_command",
    "plugins_command",
    "prune_command",
    "run_command",
    "validate_command",
    "version_command",
]
