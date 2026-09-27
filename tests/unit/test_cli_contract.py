"""Unit tests for the M43 CLI machine-contract inventory."""

from pyworkflowkit.cli_contract import (
    CLI_COMMANDS,
    CLI_ERROR_REQUIRED_KEYS,
    CLI_JSON_COMMANDS,
    CLI_JSON_NESTED_REQUIRED_KEYS,
    CLI_JSON_REQUIRED_KEYS,
)


def test_every_json_command_has_a_top_level_contract() -> None:
    assert set(CLI_JSON_REQUIRED_KEYS) == set(CLI_JSON_COMMANDS)


def test_version_is_the_only_v1_command_without_json_contract() -> None:
    assert set(CLI_COMMANDS) - set(CLI_JSON_COMMANDS) == {"version"}


def test_error_contract_is_small_and_shared() -> None:
    assert CLI_ERROR_REQUIRED_KEYS == {"error", "exit_code"}


def test_manifest_nested_contracts_cover_portable_evidence_collections() -> None:
    assert {
        "manifest.tasks[]",
        "manifest.tasks[].attempts[]",
        "manifest.tasks[].artifacts[]",
        "manifest.tasks[].external_refs[]",
        "manifest.events[]",
    } <= set(CLI_JSON_NESTED_REQUIRED_KEYS)
