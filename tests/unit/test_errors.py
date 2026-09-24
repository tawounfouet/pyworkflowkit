"""Tests for the public exception root."""

from pyworkflowkit.errors import PyWorkflowKitError


def test_public_error_root_is_catchable_as_exception() -> None:
    error = PyWorkflowKitError("boom")

    assert isinstance(error, Exception)
    assert str(error) == "boom"
