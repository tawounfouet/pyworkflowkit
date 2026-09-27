"""M43 reference acceptance for CLI machine contract v1."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

from typer.testing import CliRunner

import pyworkflowkit
from pyworkflowkit import TaskHandle, task, workflow
from pyworkflowkit.cli import (
    DOCTOR_FAILURE_EXIT,
    RUN_FAILURE_EXIT,
    VALIDATION_EXIT,
    app,
)
from pyworkflowkit.cli_contract import (
    CLI_COMMANDS,
    CLI_ERROR_REQUIRED_KEYS,
    CLI_EXIT_CODES,
    CLI_JSON_COMMANDS,
    CLI_JSON_NESTED_REQUIRED_KEYS,
    CLI_JSON_REQUIRED_KEYS,
    CLI_MACHINE_CONTRACT_VERSION,
)
from pyworkflowkit.plugins import PLUGIN_API_VERSION

runner = CliRunner()


def _install_fixture_module(monkeypatch) -> str:  # type: ignore[no-untyped-def]
    module_name = "pyworkflowkit_m43_cli_fixture"
    module = ModuleType(module_name)

    @task
    def fetch() -> str:
        return "raw"

    @task(depends_on=(fetch,))
    def publish() -> str:
        return "done"

    @workflow(id="cli.m43", version="1")
    def demo() -> tuple[TaskHandle, ...]:
        return (fetch, publish)

    module.demo = demo  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, module)
    return f"{module_name}:demo"


def _sqlite_config(tmp_path: Path) -> Path:
    path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "workspace").as_posix()
    path.write_text(
        (
            f'[runtime]\nworkspace = "{workspace}"\n'
            '[metadata]\nbackend = "sqlite"\nsqlite_path = "runtime.sqlite3"\n'
            "sqlite_wal = false\n"
        ),
        encoding="utf-8",
    )
    return path


def _command_names() -> set[str]:
    names: set[str] = set()
    for command in app.registered_commands:
        if command.name is not None:
            names.add(command.name)
        else:
            assert command.callback is not None
            names.add(command.callback.__name__.replace("_", "-"))
    return names


def test_m43_contract_version_commands_and_exit_codes_are_frozen() -> None:
    assert CLI_MACHINE_CONTRACT_VERSION == "1"
    assert _command_names() == set(CLI_COMMANDS)
    assert {
        "doctor",
        "events",
        "inspect",
        "manifest",
        "plan",
        "plugins",
        "run",
        "validate",
    } == CLI_JSON_COMMANDS
    assert dict(CLI_EXIT_CODES) == {
        "success": 0,
        "validation": 2,
        "run_failure": 3,
        "doctor_failure": 4,
    }
    assert CLI_EXIT_CODES["validation"] == VALIDATION_EXIT
    assert CLI_EXIT_CODES["run_failure"] == RUN_FAILURE_EXIT
    assert CLI_EXIT_CODES["doctor_failure"] == DOCTOR_FAILURE_EXIT


def test_m43_validate_plan_and_error_shapes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    target = _install_fixture_module(monkeypatch)

    validated = runner.invoke(app, ["validate", target, "--json"])
    planned = runner.invoke(app, ["plan", target, "--json"])
    invalid = runner.invoke(app, ["validate", "not-a-reference", "--json"])

    validate_payload = json.loads(validated.stdout)
    plan_payload = json.loads(planned.stdout)
    error_payload = json.loads(invalid.stderr)

    assert validated.exit_code == CLI_EXIT_CODES["success"]
    assert set(validate_payload) == CLI_JSON_REQUIRED_KEYS["validate"]

    assert planned.exit_code == CLI_EXIT_CODES["success"]
    assert set(plan_payload) == CLI_JSON_REQUIRED_KEYS["plan"]
    assert plan_payload["groups"]
    assert set(plan_payload["groups"][0]) == CLI_JSON_NESTED_REQUIRED_KEYS["plan.groups[]"]

    assert invalid.exit_code == CLI_EXIT_CODES["validation"]
    assert invalid.stdout == ""
    assert set(error_payload) == CLI_ERROR_REQUIRED_KEYS
    assert error_payload["exit_code"] == invalid.exit_code


def test_m43_run_inspect_events_and_manifest_shapes(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    target = _install_fixture_module(monkeypatch)
    config = _sqlite_config(tmp_path)

    executed = runner.invoke(app, ["run", target, "--config", str(config), "--json"])
    run_payload = json.loads(executed.stdout)
    run_id = run_payload["run_id"]

    inspected = runner.invoke(app, ["inspect", run_id, "--config", str(config), "--json"])
    event_result = runner.invoke(app, ["events", run_id, "--config", str(config), "--json"])
    manifest_result = runner.invoke(
        app,
        ["manifest", target, run_id, "--config", str(config), "--json"],
    )

    inspect_payload = json.loads(inspected.stdout)
    events_payload = json.loads(event_result.stdout)
    manifest_payload = json.loads(manifest_result.stdout)

    assert executed.exit_code == CLI_EXIT_CODES["success"]
    assert set(run_payload) == CLI_JSON_REQUIRED_KEYS["run"]

    assert inspected.exit_code == CLI_EXIT_CODES["success"]
    assert set(inspect_payload) == CLI_JSON_REQUIRED_KEYS["inspect"]

    assert event_result.exit_code == CLI_EXIT_CODES["success"]
    assert set(events_payload) == CLI_JSON_REQUIRED_KEYS["events"]
    assert events_payload["events"]
    assert (
        set(events_payload["events"][0])
        == CLI_JSON_NESTED_REQUIRED_KEYS["events.events[]"]
    )

    assert manifest_result.exit_code == CLI_EXIT_CODES["success"]
    assert set(manifest_payload) == CLI_JSON_REQUIRED_KEYS["manifest"]
    assert manifest_payload["schema_version"] == "1"
    assert manifest_payload["tasks"]
    assert (
        set(manifest_payload["tasks"][0])
        == CLI_JSON_NESTED_REQUIRED_KEYS["manifest.tasks[]"]
    )
    assert manifest_payload["tasks"][0]["attempts"]
    assert (
        set(manifest_payload["tasks"][0]["attempts"][0])
        == CLI_JSON_NESTED_REQUIRED_KEYS["manifest.tasks[].attempts[]"]
    )
    assert manifest_payload["events"]
    assert (
        set(manifest_payload["events"][0])
        == CLI_JSON_NESTED_REQUIRED_KEYS["manifest.events[]"]
    )


def test_m43_plugins_and_doctor_empty_inventory_shapes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "pyworkflowkit.cli.PluginDiscovery.discover",
        lambda self: (),
    )

    plugins = runner.invoke(app, ["plugins", "--json"])
    doctor = runner.invoke(app, ["doctor", "--json"])

    plugins_payload = json.loads(plugins.stdout)
    doctor_payload = json.loads(doctor.stdout)

    assert plugins.exit_code == CLI_EXIT_CODES["success"]
    assert set(plugins_payload) == CLI_JSON_REQUIRED_KEYS["plugins"]
    assert plugins_payload == {"count": 0, "plugins": []}

    assert doctor.exit_code == CLI_EXIT_CODES["success"]
    assert set(doctor_payload) == CLI_JSON_REQUIRED_KEYS["doctor"]
    assert doctor_payload["healthy"] is True
    assert doctor_payload["plugin_api_version"] == PLUGIN_API_VERSION
    assert doctor_payload["plugins"] == []


def test_m43_version_remains_plain_single_line_text() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == CLI_EXIT_CODES["success"]
    assert result.stderr == ""
    assert result.stdout == f"{pyworkflowkit.__version__}\n"
