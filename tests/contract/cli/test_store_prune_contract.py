"""Contract tests for pwk store prune command, JSON structure, and error handling."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from pyworkflowkit.authoring import TaskDefinition, WorkflowDefinition
from pyworkflowkit.cli import app
from pyworkflowkit.cli.exit_codes import ExitCode
from pyworkflowkit.executors import InlineExecutor
from pyworkflowkit.persistence import SQLiteMetadataStore
from pyworkflowkit.runtime import WorkflowRuntime
from pyworkflowkit.states import WorkflowRunStatus

runner = CliRunner()


def _populate_test_store(db_path: Path) -> None:
    workflow = WorkflowDefinition(
        name="test-contract-flow",
        tasks=(TaskDefinition(key="task-1", workload=lambda: {"msg": "hello"}),),
    )
    with SQLiteMetadataStore(db_path, wal=False) as store:
        runtime = WorkflowRuntime(executor=InlineExecutor(), metadata=store)
        res = runtime.run(workflow)
        assert res.status is WorkflowRunStatus.SUCCEEDED


def test_store_prune_help_succeeds() -> None:
    res = runner.invoke(app, ["store", "prune", "--help"])
    assert res.exit_code == int(ExitCode.SUCCESS)
    assert "--retention-days" in res.stdout
    assert "--max-runs-per-workflow" in res.stdout
    assert "--dry-run" in res.stdout
    assert "--json" in res.stdout
    assert "--db" in res.stdout


def test_store_prune_dry_run_json_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "prune_contract.sqlite3"
    _populate_test_store(db_path)

    res = runner.invoke(
        app,
        ["store", "prune", "--db", str(db_path), "--retention-days", "1", "--dry-run", "--json"],
    )
    assert res.exit_code == int(ExitCode.SUCCESS), res.stdout
    data = json.loads(res.stdout.strip())

    assert data["dry_run"] is True
    assert "scanned_workflows" in data
    assert "eligible_runs_to_prune" in data
    assert "estimated_deleted_records" in data

    records = data["estimated_deleted_records"]
    assert "workflow_runs" in records
    assert "task_runs" in records
    assert "task_attempts" in records
    assert "events" in records
    assert "checkpoints" in records


def test_store_prune_real_json_contract(tmp_path: Path) -> None:
    db_path = tmp_path / "prune_real.sqlite3"
    _populate_test_store(db_path)

    res = runner.invoke(
        app,
        ["store", "prune", "--db", str(db_path), "--retention-days", "1", "--json"],
    )
    assert res.exit_code == int(ExitCode.SUCCESS), res.stdout
    data = json.loads(res.stdout.strip())

    assert data["dry_run"] is False
    assert "scanned_workflows" in data
    assert "eligible_runs_to_prune" in data
    assert "deleted_records" in data
    assert "estimated_deleted_records" not in data


def test_store_prune_human_render(tmp_path: Path) -> None:
    db_path = tmp_path / "prune_human.sqlite3"
    _populate_test_store(db_path)

    res = runner.invoke(
        app,
        ["store", "prune", "--db", str(db_path), "--dry-run"],
    )
    assert res.exit_code == int(ExitCode.SUCCESS), res.stdout
    assert "Store Prune Report" in res.stdout
    assert "Mode" in res.stdout
    assert "Eligible Runs" in res.stdout


def test_store_prune_invalid_retention_days_json(tmp_path: Path) -> None:
    db_path = tmp_path / "invalid.sqlite3"
    res = runner.invoke(
        app,
        ["store", "prune", "--db", str(db_path), "--retention-days", "0", "--json"],
    )
    assert res.exit_code == int(ExitCode.USER_ERROR)
    err_data = json.loads(res.stderr.strip())
    assert "error" in err_data
    assert err_data["exit_code"] == int(ExitCode.USER_ERROR)


def test_store_prune_invalid_state_json(tmp_path: Path) -> None:
    db_path = tmp_path / "invalid_state.sqlite3"
    res = runner.invoke(
        app,
        ["store", "prune", "--db", str(db_path), "--state", "NON_EXISTENT", "--json"],
    )
    assert res.exit_code == int(ExitCode.USER_ERROR)
    err_data = json.loads(res.stderr.strip())
    assert "error" in err_data
    assert "Invalid workflow status" in err_data["error"]


def test_store_prune_non_terminal_state_rejected(tmp_path: Path) -> None:
    db_path = tmp_path / "non_terminal.sqlite3"
    res = runner.invoke(
        app,
        ["store", "prune", "--db", str(db_path), "--state", "RUNNING", "--json"],
    )
    assert res.exit_code == int(ExitCode.USER_ERROR)
    err_data = json.loads(res.stderr.strip())
    assert "Only terminal workflow statuses" in err_data["error"]


def test_store_prune_invalid_options_human_render(tmp_path: Path) -> None:
    db_path = tmp_path / "invalid_human.sqlite3"
    res = runner.invoke(
        app,
        ["store", "prune", "--db", str(db_path), "--state", "NON_EXISTENT"],
    )
    assert res.exit_code == int(ExitCode.USER_ERROR)
    assert "ERROR" in res.stderr or "ERROR" in res.stdout

    res2 = runner.invoke(
        app,
        ["store", "prune", "--db", str(db_path), "--retention-days", "0"],
    )
    assert res2.exit_code == int(ExitCode.USER_ERROR)
    assert "ERROR" in res2.stderr or "ERROR" in res2.stdout


def test_store_prune_store_error_handling(tmp_path: Path) -> None:
    from unittest.mock import patch

    from pyworkflowkit.errors import PyWorkflowKitError

    db_path = tmp_path / "store_err.sqlite3"
    with patch(
        "pyworkflowkit.cli.commands.prune.PruneService.prune",
        side_effect=PyWorkflowKitError("Simulated disk error"),
    ):
        res_json = runner.invoke(
            app,
            ["store", "prune", "--db", str(db_path), "--json"],
        )
        assert res_json.exit_code == int(ExitCode.STORE_ERROR)
        err_data = json.loads(res_json.stderr.strip())
        assert "Simulated disk error" in err_data["error"]

        res_human = runner.invoke(
            app,
            ["store", "prune", "--db", str(db_path)],
        )
        assert res_human.exit_code == int(ExitCode.STORE_ERROR)
        assert "ERROR" in res_human.stderr or "ERROR" in res_human.stdout
