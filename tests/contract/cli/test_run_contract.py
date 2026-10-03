"""Contract tests for pwk run command and dry-run simulation."""

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
from pyworkflowkit.cli_contract import CLI_JSON_REQUIRED_KEYS

runner = CliRunner()


def _setup_fixture(monkeypatch: pytest.MonkeyPatch, name: str) -> tuple[str, str]:
    mod = ModuleType(name)

    called_tasks: list[str] = []

    @task
    def step_success() -> str:
        called_tasks.append("step_success")
        return "ok"

    @task
    def step_failure() -> str:
        called_tasks.append("step_failure")
        raise RuntimeError("simulated task execution failure")

    @workflow(id="good.flow", version="1.0")
    def good_flow() -> tuple[TaskHandle, ...]:
        return (step_success,)

    @workflow(id="bad.flow", version="1.0")
    def bad_flow() -> tuple[TaskHandle, ...]:
        return (step_failure,)

    mod.good_flow = good_flow  # type: ignore[attr-defined]
    mod.bad_flow = bad_flow  # type: ignore[attr-defined]
    mod.called_tasks = called_tasks  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, mod)
    return f"{name}:good_flow", f"{name}:bad_flow"


def test_run_contract_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    good_target, _ = _setup_fixture(monkeypatch, "mod_run_contract_ok")
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "ws").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n'
        '[metadata]\nbackend = "sqlite"\nsqlite_path = "run.sqlite3"\n',
        encoding="utf-8",
    )

    res = runner.invoke(app, ["run", good_target, "--config", str(config_path), "--json"])
    assert res.exit_code == int(ExitCode.SUCCESS)
    data = json.loads(res.stdout)
    assert set(data) == CLI_JSON_REQUIRED_KEYS["run"]
    assert data["status"] == "SUCCEEDED"


def test_run_contract_dry_run_does_not_execute_real_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod_name = "mod_run_contract_dry"
    good_target, bad_target = _setup_fixture(monkeypatch, mod_name)
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "ws").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n'
        '[metadata]\nbackend = "sqlite"\nsqlite_path = "run.sqlite3"\n',
        encoding="utf-8",
    )

    # Even the bad flow succeeds in dry run because the failing handler is not invoked!
    res = runner.invoke(
        app,
        ["run", bad_target, "--config", str(config_path), "--dry-run", "--json"],
    )
    assert res.exit_code == int(ExitCode.SUCCESS)
    data = json.loads(res.stdout)
    assert data["status"] == "SUCCEEDED"

    mod = sys.modules[mod_name]
    # The failing task was not invoked!
    assert "step_failure" not in mod.called_tasks


def test_run_contract_task_failure_returns_execution_failure_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, bad_target = _setup_fixture(monkeypatch, "mod_run_contract_fail")
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "ws").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n'
        '[metadata]\nbackend = "sqlite"\nsqlite_path = "run.sqlite3"\n',
        encoding="utf-8",
    )

    res = runner.invoke(app, ["run", bad_target, "--config", str(config_path), "--json"])
    assert res.exit_code == int(ExitCode.EXECUTION_FAILURE)
