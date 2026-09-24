"""Package bootstrap tests."""

import pyworkflowkit


def test_package_exposes_installed_version() -> None:
    assert pyworkflowkit.__version__
    assert pyworkflowkit.__version__ != "0.0.0+unknown"
