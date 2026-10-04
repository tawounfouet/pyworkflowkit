"""Store prune command for managing metadata lifecycle and historical retention."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from pyworkflowkit.cli.exit_codes import ExitCode
from pyworkflowkit.cli.services.prune_service import PruneService
from pyworkflowkit.cli_rendering import render_error, render_prune
from pyworkflowkit.errors import PyWorkflowKitError
from pyworkflowkit.persistence.retention import (
    DEFAULT_PRUNE_STATES,
    RetentionPolicy,
)
from pyworkflowkit.states.enums import WorkflowRunStatus


def prune_command(
    retention_days: Annotated[
        int | None,
        typer.Option(
            "--retention-days",
            help="Purge runs older than this many days (completed runs).",
        ),
    ] = 30,
    max_runs_per_workflow: Annotated[
        int | None,
        typer.Option(
            "--max-runs-per-workflow",
            help="Keep at most this many recent runs per workflow name.",
        ),
    ] = 100,
    retain_failed_runs_days: Annotated[
        int | None,
        typer.Option(
            "--retain-failed-runs-days",
            help="Extended retention window in days for FAILED runs.",
        ),
    ] = 90,
    workflow: Annotated[
        list[str] | None,
        typer.Option(
            "--workflow",
            "-w",
            help="Optional workflow name(s) to restrict pruning to (repeatable).",
        ),
    ] = None,
    state: Annotated[
        list[str] | None,
        typer.Option(
            "--state",
            "-s",
            help="Eligible terminal status(es) to prune (e.g. SUCCEEDED, CANCELLED, FAILED).",
        ),
    ] = None,
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            help="Number of workflow runs to prune per transaction batch.",
        ),
    ] = 500,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Simulate pruning and estimate rows without deleting data.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emit machine-readable JSON report.",
        ),
    ] = False,
    db: Annotated[
        Path | None,
        typer.Option(
            "--db",
            help="Explicit SQLite database path.",
        ),
    ] = None,
    dsn: Annotated[
        str | None,
        typer.Option(
            "--dsn",
            help="Explicit PostgreSQL DSN connection string.",
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            help="Runtime configuration TOML file path.",
        ),
    ] = None,
) -> None:
    """Prune historical workflow runs and associated metadata according to retention policy."""
    prune_states = list(DEFAULT_PRUNE_STATES)
    if state:
        parsed_states: list[WorkflowRunStatus] = []
        for s in state:
            s_upper = s.strip().upper()
            try:
                parsed_states.append(WorkflowRunStatus(s_upper))
            except ValueError:
                err = (
                    f"Invalid workflow status '{s}'. "
                    "Valid choices are: SUCCEEDED, FAILED, CANCELLED."
                )
                if json_output:
                    typer.echo(
                        json.dumps({"error": err, "exit_code": int(ExitCode.USER_ERROR)}),
                        err=True,
                    )
                else:
                    render_error(err)
                raise typer.Exit(int(ExitCode.USER_ERROR)) from None
        prune_states = parsed_states

    try:
        policy = RetentionPolicy(
            retention_days=retention_days,
            max_runs_per_workflow=max_runs_per_workflow,
            prune_states=tuple(prune_states),
            retain_failed_runs_days=retain_failed_runs_days,
            workflow_names=tuple(workflow) if workflow else None,
        )
    except (ValueError, TypeError) as exc:
        err = f"Invalid retention policy: {exc}"
        if json_output:
            typer.echo(
                json.dumps({"error": err, "exit_code": int(ExitCode.USER_ERROR)}),
                err=True,
            )
        else:
            render_error(err)
        raise typer.Exit(int(ExitCode.USER_ERROR)) from None

    service = PruneService()
    try:
        report = service.prune(
            policy,
            dry_run=dry_run,
            batch_size=batch_size,
            db_path=db,
            dsn=dsn,
            config_path=config,
        )
    except (PyWorkflowKitError, ValueError, RuntimeError, OSError) as exc:
        err = f"Store prune failed: {exc}"
        if json_output:
            typer.echo(
                json.dumps({"error": err, "exit_code": int(ExitCode.STORE_ERROR)}),
                err=True,
            )
        else:
            render_error(err)
        raise typer.Exit(int(ExitCode.STORE_ERROR)) from None

    payload = report.to_dict()

    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        render_prune(payload, title="Store Prune Report")


__all__ = ["prune_command"]
