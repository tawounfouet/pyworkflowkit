"""Tests verifying that active CLI implementations match the frozen cli_contract_v1.json."""

from __future__ import annotations

import json

from pyworkflowkit.cli.public_contract import (
    CLI_CONTRACT_PATH,
    active_cli_command_names,
    verify_cli_contract_parity,
)
from pyworkflowkit.cli_contract import CLI_COMMANDS


def test_cli_contract_file_exists() -> None:
    assert CLI_CONTRACT_PATH.is_file()


def test_cli_contract_is_valid_json() -> None:
    content = CLI_CONTRACT_PATH.read_text(encoding="utf-8")
    data = json.loads(content)
    assert isinstance(data, dict)
    assert data["contract_version"] == "1"


def test_active_commands_match_frozen_contract() -> None:
    active_commands = active_cli_command_names()
    assert active_commands == set(CLI_COMMANDS)


def test_cli_contract_parity_enforced() -> None:
    assert verify_cli_contract_parity() is True
