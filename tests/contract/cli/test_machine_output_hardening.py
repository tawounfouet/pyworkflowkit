"""Tests verifying machine output purity and hardening on stdout/stderr."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from typer.testing import CliRunner

from pyworkflowkit._compat.v1_root import TaskHandle, task, workflow
from pyworkflowkit.cli import app
from pyworkflowkit.cli.exit_codes import ExitCode
from pyworkflowkit.cli_contract import CLI_ERROR_REQUIRED_KEYS, CLI_JSON_REQUIRED_KEYS

runner = CliRunner()


def _setup_fixture(monkeypatch: pytest.MonkeyPatch, name: str) -> str:
    mod = ModuleType(name)

    @task
    def t1() -> str:
        return "1"

    @workflow(id="purity.flow", version="1.0")
    def purity_flow() -> tuple[TaskHandle, ...]:
        return (t1,)

    mod.purity_flow = purity_flow  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, mod)
    return f"{name}:purity_flow"


def test_validate_stdout_is_strictly_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    target = _setup_fixture(monkeypatch, "mod_purity_validate")
    res = runner.invoke(app, ["validate", target, "--json"])

    assert res.exit_code == int(ExitCode.SUCCESS)
    # Output must parse as pure JSON with no leading/trailing junk
    data = json.loads(res.stdout.strip())
    assert set(data) == CLI_JSON_REQUIRED_KEYS["validate"]
    assert res.stderr == ""


def test_plan_stdout_is_strictly_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    target = _setup_fixture(monkeypatch, "mod_purity_plan")
    res = runner.invoke(app, ["plan", target, "--json"])

    assert res.exit_code == int(ExitCode.SUCCESS)
    data = json.loads(res.stdout.strip())
    assert set(data) == CLI_JSON_REQUIRED_KEYS["plan"]
    assert res.stderr == ""


def test_run_stdout_is_strictly_valid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = _setup_fixture(monkeypatch, "mod_purity_run")
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "ws").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n'
        '[metadata]\nbackend = "sqlite"\nsqlite_path = "run.sqlite3"\n',
        encoding="utf-8",
    )

    res = runner.invoke(app, ["run", target, "--config", str(config_path), "--json"])
    assert res.exit_code == int(ExitCode.SUCCESS)
    data = json.loads(res.stdout.strip())
    assert set(data) == CLI_JSON_REQUIRED_KEYS["run"]
    assert res.stderr == ""


def test_error_is_strictly_routed_to_stderr_as_json() -> None:
    res = runner.invoke(app, ["validate", "invalid_module:invalid_wf", "--json"])
    assert res.exit_code == int(ExitCode.VALIDATION_ERROR)
    assert res.stdout == ""
    err_data = json.loads(res.stderr.strip())
    assert set(err_data) == CLI_ERROR_REQUIRED_KEYS
