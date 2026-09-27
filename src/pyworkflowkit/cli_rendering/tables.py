"""Table-oriented human CLI renderers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rich.table import Table
from rich.text import Text

from pyworkflowkit.cli_rendering.console import console


def _text(value: object) -> Text:
    return Text("-" if value is None else str(value))


def render_events(payload: Mapping[str, object]) -> None:
    table = Table(title=f"Events · run={payload['run_id']}")
    table.add_column("Seq", justify="right")
    table.add_column("Type")
    table.add_column("Task")
    table.add_column("Attempt", justify="right")
    table.add_column("Occurred at")

    values = payload.get("events", [])
    if not isinstance(values, Sequence):
        raise TypeError("events payload must be a sequence")

    for item in values:
        if not isinstance(item, Mapping):
            raise TypeError("event payload item must be a mapping")
        table.add_row(
            _text(item.get("event_sequence")),
            _text(item.get("event_type")),
            _text(item.get("task_id")),
            _text(item.get("attempt_number")),
            _text(item.get("occurred_at")),
        )

    if values:
        console().print(table)
    else:
        console().print(Text("No events recorded."))


def render_plugins(payload: Mapping[str, object]) -> None:
    values = payload.get("plugins", [])
    if not isinstance(values, Sequence):
        raise TypeError("plugins payload must be a sequence")

    if not values:
        console().print(Text("No plugins discovered."))
        return

    table = Table(title=f"Plugins · {payload.get('count', len(values))} discovered")
    table.add_column("Type")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Distribution")
    table.add_column("Provider")

    for item in values:
        if not isinstance(item, Mapping):
            raise TypeError("plugin payload item must be a mapping")
        table.add_row(
            _text(item.get("type")),
            _text(item.get("name")),
            _text(item.get("status")),
            _text(item.get("distribution")),
            _text(item.get("value")),
        )
    console().print(table)


def render_doctor(payload: Mapping[str, object]) -> None:
    healthy = bool(payload.get("healthy"))
    header = Text("Healthy" if healthy else "Unhealthy", style="bold green" if healthy else "bold red")
    header.append(f" · Plugin API {payload.get('plugin_api_version', '-')}")
    console().print(header)

    values = payload.get("plugins", [])
    if not isinstance(values, Sequence):
        raise TypeError("doctor plugins payload must be a sequence")
    if not values:
        console().print(Text("No plugins selected or discovered."))
        return

    table = Table(title="Plugin Diagnostics")
    table.add_column("Type")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Error")
    for item in values:
        if not isinstance(item, Mapping):
            raise TypeError("doctor plugin payload item must be a mapping")
        table.add_row(
            _text(item.get("type")),
            _text(item.get("name")),
            _text(item.get("status")),
            _text(item.get("error")),
        )
    console().print(table)


__all__ = ["render_doctor", "render_events", "render_plugins"]
