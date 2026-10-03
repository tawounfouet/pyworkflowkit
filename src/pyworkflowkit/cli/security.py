"""Filesystem and diagnostic security helpers for PyWorkflowKit CLI."""

from __future__ import annotations

import re
import traceback
from collections.abc import Mapping
from pathlib import Path

from pyworkflowkit.cli.exit_codes import ExitCode

REDACTED = "[REDACTED]"

_SENSITIVE_NAME = (
    r"(?:password|passwd|token|secret|api[_-]?key|"
    r"credential|private[_-]?key|client[_-]?secret)"
)
_BEARER_PATTERN = re.compile(r"(?i)(\b(?:authorization|token)\b\s*[:=]\s*bearer\s+)([^\s,;]+)")
_ASSIGNMENT_PATTERN = re.compile(
    rf"""(?ix)
    (
        ["']?{_SENSITIVE_NAME}["']?
        \s*[:=]\s*
    )
    (
        "(?:\\.|[^"])*"
        |
        '(?:\\.|[^'])*'
        |
        [^\s,;]+
    )
    """
)
_URI_USERINFO_PASSWORD_PATTERN = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)([^:@/\s]+):([^/@\s]+)@")
_URI_USERINFO_SIMPLE_PATTERN = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)([^:@/\s]+)@")


class SecurityError(RuntimeError):
    """Raised when a security invariant or path boundary is violated."""

    def __init__(self, message: str, exit_code: ExitCode = ExitCode.SECURITY_ERROR) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def sanitize_input_path(raw_path: str | Path) -> Path:
    """Validate and sanitize a raw input path string, preventing null-byte attacks."""
    path_str = str(raw_path)
    if "\0" in path_str:
        raise SecurityError("Path contains prohibited null-byte character.")
    return Path(path_str)


def assert_path_within_workspace(
    path: str | Path,
    workspace_root: str | Path | None = None,
) -> Path:
    """Resolve the canonical path and assert it is strictly within the allowed workspace.

    Boundary check rejects any target that escapes the root directory.
    """
    sanitized = sanitize_input_path(path)
    resolved_target = sanitized.resolve()

    root = Path(workspace_root).resolve() if workspace_root is not None else Path.cwd().resolve()

    try:
        resolved_target.relative_to(root)
    except ValueError:
        raise SecurityError(
            f"Path '{path}' resolves outside allowed workspace boundary '{root}'."
        ) from None

    return resolved_target


def redact_text(value: str) -> str:
    """Redact sensitive credentials, passwords, tokens and database userinfo from text."""
    redacted = _URI_USERINFO_PASSWORD_PATTERN.sub(
        lambda match: f"{match.group(1)}{match.group(2)}:{REDACTED}@",
        value,
    )
    redacted = _URI_USERINFO_SIMPLE_PATTERN.sub(
        lambda match: f"{match.group(1)}{REDACTED}@",
        redacted,
    )
    redacted = _BEARER_PATTERN.sub(
        lambda match: f"{match.group(1)}{REDACTED}",
        redacted,
    )
    return _ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}{REDACTED}",
        redacted,
    )


def redact_details(details: Mapping[str, str] | None) -> dict[str, str] | None:
    """Redact a dictionary of key-value diagnostic metadata."""
    if details is None:
        return None
    return {
        key: REDACTED if re.search(_SENSITIVE_NAME, key, re.IGNORECASE) else redact_text(val)
        for key, val in details.items()
    }


def redacted_traceback(exc: BaseException) -> str:
    """Format and redact a traceback before it crosses terminal boundaries."""
    return redact_text("".join(traceback.format_exception(exc)))


__all__ = [
    "REDACTED",
    "SecurityError",
    "assert_path_within_workspace",
    "redact_details",
    "redact_text",
    "redacted_traceback",
    "sanitize_input_path",
]
