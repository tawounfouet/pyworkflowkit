"""DX02 acceptance for Rich human CLI rendering."""

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
    module_name = "pyworkflowkit_dx02_cli_fixture"
    module = ModuleType(module_name)

    @task
    def fetch() -> str:
        return "raw"

    @task(depends_on=(fetch,))
    def publish() -> str:
        return "done"

    @workflow(id="cli.rich", version="1")
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


def test_dx02_validate_and_plan_have_rich_human_surfaces(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    target = _install_fixture_module(monkeypatch)

    validated = runner.invoke(app, ["validate", target])
    planned = runner.invoke(app, ["plan", target])

    assert validated.exit_code == 0
    assert "Workflow Validation" in validated.stdout
    assert "VALID" in validated.stdout
    assert "cli.rich@1" in validated.stdout

    assert planned.exit_code == 0
    assert "Execution Plan" in planned.stdout
    assert "Stage 0" in planned.stdout
    assert "fetch" in planned.stdout
    assert "Stage 1" in planned.stdout
    assert "publish" in planned.stdout


def test_dx02_json_path_remains_plain_machine_json(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    target = _install_fixture_module(monkeypatch)

    result = runner.invoke(app, ["plan", target, "--json"])

    assert result.exit_code == 0
    assert "\x1b[" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload == {
        "groups": [
            {"index": 0, "tasks": ["fetch"]},
            {"index": 1, "tasks": ["publish"]},
        ],
        "workflow_id": "cli.rich",
        "workflow_version": "1",
    }


def test_dx02_run_inspect_events_and_manifest_render_human_output(
    tmp_path: Path,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    target = _install_fixture_module(monkeypatch)
    config = _sqlite_config(tmp_path)

    executed = runner.invoke(app, ["run", target, "--config", str(config), "--json"])
    assert executed.exit_code == 0
    run_id = json.loads(executed.stdout)["run_id"]

    run_human = runner.invoke(app, ["run", target, "--config", str(config)])
    inspected = runner.invoke(app, ["inspect", run_id, "--config", str(config)])
    events = runner.invoke(app, ["events", run_id, "--config", str(config)])
    manifest = runner.invoke(app, ["manifest", target, run_id, "--config", str(config)])

    assert run_human.exit_code == 0
    assert "Workflow Run" in run_human.stdout
    assert "SUCCEEDED" in run_human.stdout

    assert inspected.exit_code == 0
    assert "Persisted Workflow Run" in inspected.stdout
    assert run_id in inspected.stdout

    assert events.exit_code == 0
    assert "Events" in events.stdout
    assert "WORKFLOW" in events.stdout or "TASK" in events.stdout

    assert manifest.exit_code == 0
    assert "Run Manifest" in manifest.stdout
    assert run_id in manifest.stdout
    assert "Tasks" in manifest.stdout
    assert "Events" in manifest.stdout


def test_dx02_plugins_and_doctor_render_empty_human_inventory(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("pyworkflowkit.cli.PluginDiscovery.discover", lambda self: ())

    plugins = runner.invoke(app, ["plugins"])
    doctor = runner.invoke(app, ["doctor"])

    assert plugins.exit_code == 0
    assert "No plugins discovered." in plugins.stdout

    assert doctor.exit_code == 0
    assert "Healthy" in doctor.stdout
    assert "Plugin API" in doctor.stdout
    assert "No plugins selected or discovered." in doctor.stdout


def test_dx02_human_error_uses_rich_stderr_without_changing_exit_code() -> None:
    result = runner.invoke(app, ["validate", "not-a-reference"])

    assert result.exit_code == 2
    assert result.stdout == ""
    assert "ERROR" in result.stderr
    assert "module:attribute" in result.stderr
