"""M20 CLI acceptance scenarios."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType

from typer.testing import CliRunner

from pyworkflowkit import TaskHandle, task, workflow
from pyworkflowkit.cli import app

runner = CliRunner()


def _install_fixture_module(monkeypatch) -> str:  # type: ignore[no-untyped-def]
    module_name = "pyworkflowkit_cli_fixture"
    module = ModuleType(module_name)

    @task
    def fetch() -> str:
        return "raw"

    @task(depends_on=(fetch,))
    def publish() -> str:
        return "done"

    @workflow(id="cli.demo", version="1")
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


def test_cli_validate_and_plan(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    target = _install_fixture_module(monkeypatch)

    validated = runner.invoke(app, ["validate", target, "--json"])
    planned = runner.invoke(app, ["plan", target, "--json"])

    assert validated.exit_code == 0
    assert json.loads(validated.stdout)["valid"] is True
    assert planned.exit_code == 0
    assert json.loads(planned.stdout)["groups"] == [
        {"index": 0, "tasks": ["fetch"]},
        {"index": 1, "tasks": ["publish"]},
    ]


def test_cli_run_inspect_events_and_manifest(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    target = _install_fixture_module(monkeypatch)
    config = _sqlite_config(tmp_path)

    executed = runner.invoke(app, ["run", target, "--config", str(config), "--json"])
    assert executed.exit_code == 0
    run_payload = json.loads(executed.stdout)
    run_id = run_payload["run_id"]

    inspected = runner.invoke(app, ["inspect", run_id, "--config", str(config), "--json"])
    event_result = runner.invoke(app, ["events", run_id, "--config", str(config), "--json"])
    manifest_result = runner.invoke(
        app,
        ["manifest", target, run_id, "--config", str(config), "--json"],
    )

    assert inspected.exit_code == 0
    assert json.loads(inspected.stdout)["status"] == "SUCCEEDED"
    assert event_result.exit_code == 0
    assert json.loads(event_result.stdout)["events"]
    assert manifest_result.exit_code == 0
    assert json.loads(manifest_result.stdout)["status"] == "SUCCEEDED"


def test_cli_invalid_reference_has_nonzero_exit() -> None:
    result = runner.invoke(app, ["validate", "not-a-reference"])

    assert result.exit_code == 2
    assert "module:attribute" in result.stderr


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip()
