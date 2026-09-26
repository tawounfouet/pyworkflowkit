"""Structured diagnostic logging primitives for the embedded runtime."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

_SENSITIVE_TOKENS: Final[tuple[str, ...]] = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "private_key",
)
_REDACTED: Final[str] = "<redacted>"


@dataclass(frozen=True, slots=True)
class LogContext:
    """Stable correlation identifiers attached to runtime diagnostics."""

    run_id: str | None = None
    workflow_id: str | None = None
    task_run_id: str | None = None
    task_id: str | None = None
    attempt_number: int | None = None
    executor_key: str | None = None
    fields: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))

    def as_dict(self) -> dict[str, object]:
        values: dict[str, object] = {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "task_run_id": self.task_run_id,
            "task_id": self.task_id,
            "attempt_number": self.attempt_number,
            "executor_key": self.executor_key,
        }
        values.update(self.fields)
        return {
            key: redact_value(value, key=key) for key, value in values.items() if value is not None
        }


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(token in normalized for token in _SENSITIVE_TOKENS)


def redact_mapping(values: Mapping[str, object]) -> dict[str, object]:
    """Recursively redact values whose key names look sensitive."""

    return {key: redact_value(value, key=key) for key, value in values.items()}


def redact_value(value: object, *, key: str | None = None) -> object:
    """Return a log-safe representation without becoming a secret manager."""

    if key is not None and _is_sensitive_key(key):
        return _REDACTED
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    return value


def log_runtime(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    context: LogContext | None = None,
    fields: Mapping[str, object] | None = None,
) -> None:
    """Emit one structured log record using stdlib logging extras."""

    extra: dict[str, object] = {}
    if context is not None:
        extra.update(context.as_dict())
    if fields:
        extra.update(redact_mapping(fields))
    logger.log(level, message, extra={"pyworkflowkit": extra})


def structured_fields(record: logging.LogRecord) -> Mapping[str, object]:
    """Return structured PyWorkflowKit fields from a LogRecord."""

    value = getattr(record, "pyworkflowkit", {})
    if isinstance(value, Mapping):
        return value
    return {}


__all__ = [
    "LogContext",
    "log_runtime",
    "redact_mapping",
    "redact_value",
    "structured_fields",
]
