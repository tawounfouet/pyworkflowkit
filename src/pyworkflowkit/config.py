"""Validated runtime configuration with explicit source precedence."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeCoreSettings(BaseModel):
    """Core runtime settings independent from any workload domain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace: Path = Path(".pyworkflow")


class MetadataSettings(BaseModel):
    """Configuration for the runtime metadata backend."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: Literal["memory", "sqlite", "postgres"] = "memory"
    sqlite_path: Path = Path("state/pyworkflow.sqlite3")
    sqlite_busy_timeout_ms: int = Field(default=5_000, ge=0)
    sqlite_wal: bool = True
    postgres_dsn: SecretStr | None = None
    postgres_pool_size: int = Field(default=5, ge=1)
    postgres_max_overflow: int = Field(default=10, ge=0)
    postgres_application_name: str = "pyworkflowkit"

    @model_validator(mode="after")
    def validate_backend_requirements(self) -> MetadataSettings:
        if self.backend == "postgres" and self.postgres_dsn is None:
            raise ValueError("metadata.postgres_dsn is required for postgres backend")
        if not self.postgres_application_name.strip():
            raise ValueError("metadata.postgres_application_name must not be blank")
        return self


class RuntimeSettings(BaseSettings):
    """Top-level settings for composing a PyWorkflowKit runtime.

    Source precedence is:
        explicit overrides > TOML file > environment variables > defaults
    """

    model_config = SettingsConfigDict(
        env_prefix="PYWORKFLOWKIT_",
        env_nested_delimiter="__",
        extra="forbid",
        frozen=True,
    )

    runtime: RuntimeCoreSettings = Field(default_factory=RuntimeCoreSettings)
    metadata: MetadataSettings = Field(default_factory=MetadataSettings)

    @classmethod
    def load(
        cls,
        *,
        config_file: str | Path | None = None,
        overrides: Mapping[str, object] | None = None,
    ) -> RuntimeSettings:
        """Load settings using the documented precedence contract."""

        env_and_defaults = cls()
        merged: dict[str, Any] = env_and_defaults.model_dump()

        if config_file is not None:
            path = Path(config_file)
            with path.open("rb") as stream:
                file_values = tomllib.load(stream)
            merged = _deep_merge(merged, file_values)

        if overrides:
            merged = _deep_merge(merged, dict(overrides))

        return cls.model_validate(merged)

    def redacted_dict(self) -> dict[str, object]:
        """Return settings safe for diagnostics and logging."""

        redacted = _redact(self.model_dump())
        if not isinstance(redacted, dict):
            raise TypeError("redacted runtime settings must remain a mapping")
        return redacted


def _deep_merge(
    base: Mapping[str, Any],
    overlay: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        existing = result.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            result[key] = _deep_merge(existing, value)
        else:
            result[key] = value
    return result


def _redact(value: object) -> object:
    if isinstance(value, SecretStr):
        return "**********"
    if isinstance(value, Mapping):
        return {str(key): _redact(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    return value


__all__ = [
    "MetadataSettings",
    "RuntimeCoreSettings",
    "RuntimeSettings",
]
