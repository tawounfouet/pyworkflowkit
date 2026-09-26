"""Package metadata consistency checks."""

from importlib.metadata import version

from typer.testing import CliRunner

import pyworkflowkit
from pyworkflowkit.cli import app


def test_package_metadata_matches_public_version() -> None:
    assert pyworkflowkit.__version__ == version("pyworkflowkit")


def test_cli_version_matches_package_metadata() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == version("pyworkflowkit")
