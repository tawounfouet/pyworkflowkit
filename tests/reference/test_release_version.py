"""0.5.0a1 development metadata consistency checks."""

from importlib.metadata import version

from typer.testing import CliRunner

import pyworkflowkit
from pyworkflowkit.cli import app

EXPECTED_VERSION = "0.5.0a1"


def test_package_metadata_and_public_version_match_development_version() -> None:
    assert version("pyworkflowkit") == EXPECTED_VERSION
    assert pyworkflowkit.__version__ == EXPECTED_VERSION


def test_cli_version_matches_development_version() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == EXPECTED_VERSION
