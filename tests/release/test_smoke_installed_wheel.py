"""Smoke test verifying public surface and CLI commands (LOT-37 RC Gate)."""

from __future__ import annotations

import pyworkflowkit
from pyworkflowkit import (
    ExecutionPlan,
    PyWorkflowKitError,
    RetryPolicy,
    WorkflowRuntime,
)
from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.cli.public_contract import (
    active_cli_command_names,
    verify_cli_contract_parity,
)
from pyworkflowkit.cli_contract import CLI_COMMANDS


def test_public_facade_smoke() -> None:
    """Verify that public facades and symbols are intact."""
    assert pyworkflowkit.__version__
    assert TaskDefinition is not None
    assert WorkflowDefinition is not None
    assert WorkflowRuntime is not None
    assert ExecutionPlan is not None
    assert RetryPolicy is not None
    assert PyWorkflowKitError is not None


def test_cli_commands_and_contract_parity_smoke() -> None:
    """Verify that all frozen CLI commands are registered and contract parity holds."""
    active_commands = active_cli_command_names()
    assert active_commands == set(CLI_COMMANDS)
    assert verify_cli_contract_parity() is True
