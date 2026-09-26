"""Tests for validated runtime configuration and precedence."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from pyworkflowkit.config import RuntimeSettings


def test_defaults_use_memory_backend() -> None:
    settings = RuntimeSettings()

    assert settings.metadata.backend == "memory"
    assert settings.runtime.workspace == Path(".pyworkflow")


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYWORKFLOWKIT_METADATA__BACKEND", "sqlite")
    monkeypatch.setenv("PYWORKFLOWKIT_RUNTIME__WORKSPACE", "/tmp/workflows")

    settings = RuntimeSettings()

    assert settings.metadata.backend == "sqlite"
    assert settings.runtime.workspace == Path("/tmp/workflows")


def test_toml_overrides_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYWORKFLOWKIT_METADATA__BACKEND", "memory")
    config_file = tmp_path / "pyworkflowkit.toml"
    config_file.write_text(
        '[metadata]\nbackend = "sqlite"\nsqlite_path = "local.sqlite3"\n',
        encoding="utf-8",
    )

    settings = RuntimeSettings.load(config_file=config_file)

    assert settings.metadata.backend == "sqlite"
    assert settings.metadata.sqlite_path == Path("local.sqlite3")


def test_explicit_overrides_win_over_toml_and_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYWORKFLOWKIT_METADATA__BACKEND", "memory")
    config_file = tmp_path / "pyworkflowkit.toml"
    config_file.write_text('[metadata]\nbackend = "sqlite"\n', encoding="utf-8")

    settings = RuntimeSettings.load(
        config_file=config_file,
        overrides={"metadata": {"backend": "memory"}},
    )

    assert settings.metadata.backend == "memory"


def test_postgres_requires_dsn() -> None:
    with pytest.raises(ValidationError, match="postgres_dsn"):
        RuntimeSettings.model_validate({"metadata": {"backend": "postgres"}})


def test_secret_is_redacted_from_diagnostics() -> None:
    settings = RuntimeSettings.model_validate(
        {
            "metadata": {
                "backend": "postgres",
                "postgres_dsn": "postgresql+psycopg://user:secret@db/workflows",
            }
        }
    )

    redacted = settings.redacted_dict()

    assert redacted["metadata"]["postgres_dsn"] == "**********"
    assert "secret" not in repr(redacted)
