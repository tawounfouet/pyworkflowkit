"""CLI public contract reader and drift verification helper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pyworkflowkit.cli.app import app
from pyworkflowkit.cli_contract import (
    CLI_COMMANDS,
    CLI_ERROR_REQUIRED_KEYS,
    CLI_EXIT_CODES,
    CLI_JSON_COMMANDS,
    CLI_JSON_NESTED_REQUIRED_KEYS,
    CLI_JSON_REQUIRED_KEYS,
    CLI_MACHINE_CONTRACT_VERSION,
)

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"
CLI_CONTRACT_PATH = CONTRACTS_DIR / "cli_contract_v1.json"


def load_cli_contract_snapshot() -> dict[str, Any]:
    """Load the frozen CLI contract snapshot JSON file."""
    if not CLI_CONTRACT_PATH.is_file():
        raise FileNotFoundError(f"CLI contract snapshot missing at {CLI_CONTRACT_PATH}")
    return json.loads(CLI_CONTRACT_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def active_cli_command_names() -> set[str]:
    """Extract registered CLI command names from the Typer application."""
    names: set[str] = set()
    for command in app.registered_commands:
        if command.name is not None:
            names.add(command.name)
        elif command.callback is not None:
            names.add(command.callback.__name__.replace("_", "-"))
    return names


class CliContractMismatchError(RuntimeError):
    """Raised when active CLI definitions drift from the frozen contract."""


def verify_cli_contract_parity() -> bool:
    """Verify that active Python definitions strictly match the frozen contract JSON."""
    snapshot = load_cli_contract_snapshot()

    if snapshot["contract_version"] != CLI_MACHINE_CONTRACT_VERSION:
        raise CliContractMismatchError(
            f"Contract version mismatch: {snapshot['contract_version']} != "
            f"{CLI_MACHINE_CONTRACT_VERSION}"
        )
    if set(snapshot["commands"]) != set(CLI_COMMANDS):
        raise CliContractMismatchError(
            f"Commands mismatch: {set(snapshot['commands'])} != {set(CLI_COMMANDS)}"
        )
    if set(snapshot["json_commands"]) != CLI_JSON_COMMANDS:
        raise CliContractMismatchError(
            f"JSON commands mismatch: {set(snapshot['json_commands'])} != {CLI_JSON_COMMANDS}"
        )
    if snapshot["exit_codes"] != dict(CLI_EXIT_CODES):
        raise CliContractMismatchError(
            f"Exit codes mismatch: {snapshot['exit_codes']} != {dict(CLI_EXIT_CODES)}"
        )
    if set(snapshot["error_required_keys"]) != CLI_ERROR_REQUIRED_KEYS:
        raise CliContractMismatchError(
            f"Error keys mismatch: {set(snapshot['error_required_keys'])} != "
            f"{CLI_ERROR_REQUIRED_KEYS}"
        )

    for cmd, keys in snapshot["json_required_keys"].items():
        if cmd not in CLI_JSON_REQUIRED_KEYS or set(keys) != set(CLI_JSON_REQUIRED_KEYS[cmd]):
            raise CliContractMismatchError(
                f"JSON required keys mismatch for {cmd}: {set(keys)} != "
                f"{CLI_JSON_REQUIRED_KEYS.get(cmd)}"
            )

    for key, nested_keys in snapshot["json_nested_required_keys"].items():
        if key not in CLI_JSON_NESTED_REQUIRED_KEYS or set(nested_keys) != set(
            CLI_JSON_NESTED_REQUIRED_KEYS[key]
        ):
            raise CliContractMismatchError(
                f"Nested keys mismatch for {key}: {set(nested_keys)} != "
                f"{CLI_JSON_NESTED_REQUIRED_KEYS.get(key)}"
            )

    active_commands = active_cli_command_names()
    if active_commands != set(CLI_COMMANDS):
        raise CliContractMismatchError(
            f"Active CLI commands mismatch: {active_commands} != {set(CLI_COMMANDS)}"
        )
    return True


__all__ = [
    "CLI_CONTRACT_PATH",
    "CliContractMismatchError",
    "active_cli_command_names",
    "load_cli_contract_snapshot",
    "verify_cli_contract_parity",
]
