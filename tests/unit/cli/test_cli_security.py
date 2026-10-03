"""Unit tests for CLI security boundaries and credential redaction."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyworkflowkit.cli.security import (
    REDACTED,
    SecurityError,
    assert_path_within_workspace,
    redact_details,
    redact_text,
    sanitize_input_path,
)


def test_sanitize_input_path_valid() -> None:
    path = sanitize_input_path("workflows/pipeline.py")
    assert path == Path("workflows/pipeline.py")


def test_sanitize_input_path_rejects_null_bytes() -> None:
    with pytest.raises(SecurityError, match="prohibited null-byte"):
        sanitize_input_path("workflows/\0pipeline.py")


def test_assert_path_within_workspace_valid(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target_file = workspace / "sub" / "workflow.py"
    target_file.parent.mkdir()
    target_file.touch()

    safe = assert_path_within_workspace(target_file, workspace_root=workspace)
    assert safe == target_file.resolve()


def test_assert_path_within_workspace_rejects_traversal(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside_file = tmp_path / "secret.py"
    outside_file.touch()

    traversal_path = workspace / ".." / "secret.py"

    with pytest.raises(SecurityError, match="resolves outside allowed workspace"):
        assert_path_within_workspace(traversal_path, workspace_root=workspace)


def test_redact_text_masks_credentials_and_dsn() -> None:
    text = "Connecting to postgresql://admin:super_secret_password@db.example.com:5432/analytics"
    redacted = redact_text(text)
    assert "super_secret_password" not in redacted
    assert f"postgresql://admin:{REDACTED}@db.example.com:5432/analytics" in redacted


def test_redact_text_masks_bearer_token() -> None:
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token"
    redacted = redact_text(text)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token" not in redacted
    assert f"Authorization: Bearer {REDACTED}" in redacted


def test_redact_details_masks_sensitive_keys() -> None:
    details = {
        "api_key": "12345-secret",
        "normal_field": "public_value",
    }
    redacted = redact_details(details)
    assert redacted is not None
    assert redacted["api_key"] == REDACTED
    assert redacted["normal_field"] == "public_value"
