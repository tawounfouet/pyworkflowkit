"""Contract tests for pwk store prune command, JSON structure, and error handling."""

from __future__ import annotations

import json
import re
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


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)


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
    res = runner.invoke(app, ["store", "prune", "--help"], color=False)
    assert res.exit_code == int(ExitCode.SUCCESS)
    plain = _strip_ansi(res.stdout)
    assert "--retention-days" in plain
    assert "--max-runs-per-workflow" in plain
    assert "--dry-run" in plain
    assert "--json" in plain
    assert "--db" in plain


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
        color=False,
    )
    assert res.exit_code == int(ExitCode.SUCCESS), res.stdout
    plain = _strip_ansi(res.stdout)
    assert "Store Prune Report" in plain
    assert "Mode" in plain
    assert "Eligible Runs" in plain


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
        color=False,
    )
    assert res.exit_code == int(ExitCode.USER_ERROR)
    plain = _strip_ansi(res.stderr + res.stdout)
    assert "ERROR" in plain

    res2 = runner.invoke(
        app,
        ["store", "prune", "--db", str(db_path), "--retention-days", "0"],
        color=False,
    )
    assert res2.exit_code == int(ExitCode.USER_ERROR)
    plain2 = _strip_ansi(res2.stderr + res2.stdout)
    assert "ERROR" in plain2


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
            color=False,
        )
        assert res_human.exit_code == int(ExitCode.STORE_ERROR)
        plain_err = _strip_ansi(res_human.stderr + res_human.stdout)
        assert "ERROR" in plain_err
