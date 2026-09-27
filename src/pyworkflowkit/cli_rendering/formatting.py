"""Panel-oriented human CLI renderers."""

from __future__ import annotations

from collections.abc import Mapping

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pyworkflowkit.cli_rendering.console import console


def _value(value: object) -> str:
    return "-" if value is None else str(value)


def render_validation(payload: Mapping[str, object]) -> None:
    body = Text()
    body.append("VALID\n", style="bold green")
    body.append(f"{_value(payload['workflow_id'])}@{_value(payload['workflow_version'])}")
    body.append(f"  ·  {_value(payload['task_count'])} task(s)")
    console().print(Panel.fit(body, title="Workflow Validation"))


def render_run(payload: Mapping[str, object], *, title: str = "Workflow Run") -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    rows = (
        ("Workflow", f"{_value(payload['workflow_id'])}@{_value(payload['workflow_version'])}"),
        ("Run", _value(payload["run_id"])),
        ("Status", _value(payload["status"])),
        ("Created", _value(payload.get("created_at"))),
        ("Started", _value(payload.get("started_at"))),
        ("Finished", _value(payload.get("finished_at"))),
    )
    for key, value in rows:
        table.add_row(Text(key), Text(value))
    console().print(Panel.fit(table, title=title))


def render_manifest(payload: Mapping[str, object]) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    rows = (
        ("Workflow", f"{_value(payload['workflow_id'])}@{_value(payload['workflow_version'])}"),
        ("Run", _value(payload["run_id"])),
        ("Status", _value(payload["status"])),
        ("Tasks", _value(payload["task_count"])),
        ("Events", _value(payload["event_count"])),
    )
    for key, value in rows:
        table.add_row(Text(key), Text(value))
    console().print(Panel.fit(table, title="Run Manifest"))


def render_error(message: str) -> None:
    text = Text()
    text.append("ERROR", style="bold red")
    text.append(f": {message}")
    console(error=True).print(text)


__all__ = ["render_error", "render_manifest", "render_run", "render_validation"]
