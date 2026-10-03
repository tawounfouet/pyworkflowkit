"""Doctor command for PyWorkflowKit environment and plugin diagnostics."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from pyworkflowkit.cli.exit_codes import ExitCode
from pyworkflowkit.cli.services.doctor_service import DoctorService
from pyworkflowkit.cli_rendering import render_doctor
from pyworkflowkit.errors import PyWorkflowKitError
from pyworkflowkit.plugins import PluginType


def _parse_plugin_enablements(
    value: str | None,
) -> dict[PluginType, tuple[str, ...]]:
    if value is None or not value.strip():
        return {}

    parsed: dict[PluginType, list[str]] = {}
    for raw_selector in value.split(","):
        selector = raw_selector.strip()
        type_name, separator, plugin_name = selector.partition(":")
        if not separator or not type_name or not plugin_name:
            raise ValueError(
                "plugin selector must use type:name syntax (executor, metadata, workload, or event)"
            )
        try:
            plugin_type = PluginType(type_name)
        except ValueError as exc:
            supported = ", ".join(t.value for t in PluginType)
            raise ValueError(
                f"unsupported plugin type '{type_name}'. Supported: {supported}"
            ) from exc

        parsed.setdefault(plugin_type, []).append(plugin_name)

    return {k: tuple(v) for k, v in parsed.items()}


def doctor_command(
    enable: Annotated[
        str | None,
        typer.Option(
            "--enable",
            help="Comma-separated explicit plugin selectors, e.g. executor:custom.",
        ),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON.")
    ] = False,
) -> None:
    """Check environment readiness, store backends, and plugin compatibility."""
    service = DoctorService()

    try:
        enabled = _parse_plugin_enablements(enable)
        diagnosis = service.run_full_diagnosis(enabled_selectors=enabled if enabled else None)
    except (PyWorkflowKitError, ValueError) as exc:
        if json_output:
            typer.echo(
                json.dumps(
                    {"error": str(exc), "exit_code": int(ExitCode.DOCTOR_FAILURE)},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                err=True,
            )
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(int(ExitCode.DOCTOR_FAILURE)) from None

    payload: dict[str, object] = {
        "healthy": diagnosis["healthy"],
        "plugin_api_version": diagnosis["plugin_api_version"],
        "plugins": diagnosis["plugins"],
    }

    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str))
    else:
        render_doctor(payload)

    if not diagnosis["healthy"]:
        raise typer.Exit(int(ExitCode.DOCTOR_FAILURE))


__all__ = ["doctor_command"]
