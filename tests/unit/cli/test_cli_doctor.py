"""Unit tests for CLI doctor service and commands."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from pyworkflowkit import __version__
from pyworkflowkit.cli.app import app
from pyworkflowkit.cli.services.doctor_service import DoctorService

runner = CliRunner()


def test_doctor_service_diagnose_environment() -> None:
    service = DoctorService()
    diag = service.diagnose_environment()

    assert diag["pyworkflowkit_version"] == __version__
    assert "python_version" in diag
    assert "platform" in diag
    assert "stores" in diag
    assert diag["stores"]["memory"]["available"] is True
    assert diag["stores"]["sqlite"]["available"] is True


def test_doctor_command_json_output() -> None:
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["healthy"] is True
    assert payload["plugin_api_version"] == "1"
    assert "plugins" in payload


def test_version_command_plain_and_json() -> None:
    plain_result = runner.invoke(app, ["version"])
    assert plain_result.exit_code == 0
    assert __version__ in plain_result.stdout

    json_result = runner.invoke(app, ["version", "--json"])
    assert json_result.exit_code == 0
    payload = json.loads(json_result.stdout)
    assert payload["version"] == __version__
