"""Unit tests for validate, plan, and inspect CLI commands."""

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

runner = CliRunner()


def _setup_fixture(monkeypatch: pytest.MonkeyPatch, name: str) -> str:
    mod = ModuleType(name)

    @task
    def t1() -> str:
        return "1"

    @task(depends_on=(t1,))
    def t2() -> str:
        return "2"

    @workflow(id="cmd.flow", version="1.5")
    def my_flow() -> tuple[TaskHandle, ...]:
        return (t1, t2)

    mod.my_flow = my_flow  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, name, mod)
    return f"{name}:my_flow"


def test_cli_validate_success(monkeypatch: pytest.MonkeyPatch) -> None:
    target = _setup_fixture(monkeypatch, "mod_cli_validate_ok")

    # JSON mode
    res = runner.invoke(app, ["validate", target, "--json"])
    assert res.exit_code == int(ExitCode.SUCCESS)
    data = json.loads(res.stdout)
    assert data["valid"] is True
    assert data["workflow_id"] == "cmd.flow"
    assert data["workflow_version"] == "1.5"
    assert data["task_count"] == 2

    # Human mode
    res_human = runner.invoke(app, ["validate", target])
    assert res_human.exit_code == int(ExitCode.SUCCESS)


def test_cli_validate_failure() -> None:
    res = runner.invoke(app, ["validate", "invalid_module:invalid_attr", "--json"])
    assert res.exit_code == int(ExitCode.VALIDATION_ERROR)
    err = json.loads(res.stderr)
    assert "error" in err
    assert err["exit_code"] == int(ExitCode.VALIDATION_ERROR)


def test_cli_plan_formats(monkeypatch: pytest.MonkeyPatch) -> None:
    target = _setup_fixture(monkeypatch, "mod_cli_plan_formats")

    # JSON mode
    res_json = runner.invoke(app, ["plan", target, "--json"])
    assert res_json.exit_code == int(ExitCode.SUCCESS)
    data = json.loads(res_json.stdout)
    assert data["workflow_id"] == "cmd.flow"
    assert len(data["groups"]) == 2

    # Mermaid mode via flag
    res_mermaid = runner.invoke(app, ["plan", target, "--mermaid"])
    assert res_mermaid.exit_code == int(ExitCode.SUCCESS)
    assert "graph TD" in res_mermaid.stdout
    assert "t1" in res_mermaid.stdout
    assert "t2" in res_mermaid.stdout

    # Mermaid mode via --format
    res_format_mermaid = runner.invoke(app, ["plan", target, "--format", "mermaid"])
    assert res_format_mermaid.exit_code == int(ExitCode.SUCCESS)
    assert "graph TD" in res_format_mermaid.stdout

    # ASCII mode via flag
    res_ascii = runner.invoke(app, ["plan", target, "--ascii"])
    assert res_ascii.exit_code == int(ExitCode.SUCCESS)
    assert "Stage 0:" in res_ascii.stdout
    assert "Stage 1:" in res_ascii.stdout

    # Human mode
    res_human = runner.invoke(app, ["plan", target])
    assert res_human.exit_code == int(ExitCode.SUCCESS)


def test_cli_inspect_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = _setup_fixture(monkeypatch, "mod_cli_inspect_flow")
    config_path = tmp_path / "pyworkflowkit.toml"
    workspace = (tmp_path / "workspace").as_posix()
    config_path.write_text(
        f'[runtime]\nworkspace = "{workspace}"\n'
        '[metadata]\nbackend = "sqlite"\nsqlite_path = "run.sqlite3"\n',
        encoding="utf-8",
    )

    # First run the workflow
    run_res = runner.invoke(app, ["run", target, "--config", str(config_path), "--json"])
    assert run_res.exit_code == int(ExitCode.SUCCESS)
    run_id = json.loads(run_res.stdout)["run_id"]

    # Inspect with JSON
    insp_res = runner.invoke(app, ["inspect", run_id, "--config", str(config_path), "--json"])
    assert insp_res.exit_code == int(ExitCode.SUCCESS)
    data = json.loads(insp_res.stdout)
    assert data["run_id"] == run_id
    assert data["workflow_id"] == "cmd.flow"
    assert data["status"] == "SUCCEEDED"

    # Inspect human
    insp_human = runner.invoke(app, ["inspect", run_id, "--config", str(config_path)])
    assert insp_human.exit_code == int(ExitCode.SUCCESS)

    # Inspect non-existent run
    err_res = runner.invoke(app, ["inspect", "no-such-run", "--config", str(config_path), "--json"])
    assert err_res.exit_code == int(ExitCode.VALIDATION_ERROR)
