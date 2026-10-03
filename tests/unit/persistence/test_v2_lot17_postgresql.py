"""Unit qualification for LOT-17 canonical PostgreSQL persistence."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.engine import URL

import pyworkflowkit.persistence.postgresql as postgresql
from pyworkflowkit.persistence.postgresql import (
    DEFAULT_V2_POSTGRES_APPLICATION_NAME,
    PostgreSQLSettings,
    create_postgresql_engine,
)


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"dsn": ""}, ValueError),
        ({"dsn": 42}, TypeError),
        ({"dsn": "postgresql://example", "pool_size": 0}, ValueError),
        ({"dsn": "postgresql://example", "pool_size": True}, TypeError),
        ({"dsn": "postgresql://example", "max_overflow": -1}, ValueError),
        ({"dsn": "postgresql://example", "max_overflow": True}, TypeError),
        ({"dsn": "postgresql://example", "application_name": ""}, ValueError),
        ({"dsn": "postgresql://example", "application_name": 42}, TypeError),
    ],
)
def test_lot17_postgresql_settings_fail_closed(
    kwargs: dict[str, object],
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        PostgreSQLSettings(**kwargs)  # type: ignore[arg-type]


def test_lot17_postgresql_settings_have_bounded_defaults() -> None:
    settings = PostgreSQLSettings("postgresql+psycopg://user:pass@db.example/pwk")

    assert settings.pool_size == 5
    assert settings.max_overflow == 10
    assert settings.application_name == DEFAULT_V2_POSTGRES_APPLICATION_NAME


def test_lot17_engine_rejects_non_postgresql_url() -> None:
    settings = PostgreSQLSettings("sqlite:///wrong.sqlite3")

    with pytest.raises(ValueError, match="PostgreSQL"):
        create_postgresql_engine(settings)


def test_lot17_engine_rejects_wrong_settings_type() -> None:
    with pytest.raises(TypeError, match="PostgreSQLSettings"):
        create_postgresql_engine(object())  # type: ignore[arg-type]


def test_lot17_engine_freezes_postgresql_connection_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    sentinel = object()

    def fake_create_engine(url: URL, **kwargs: Any) -> object:
        captured["url"] = url
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(postgresql, "create_engine", fake_create_engine)

    settings = PostgreSQLSettings(
        "postgresql+psycopg://user:pass@db.example/pwk",
        pool_size=7,
        max_overflow=3,
        application_name="lot17-tests",
    )

    engine = create_postgresql_engine(settings)

    assert engine is sentinel
    assert str(captured["url"]).startswith("postgresql+psycopg://user:")
    assert captured["pool_size"] == 7
    assert captured["max_overflow"] == 3
    assert captured["pool_pre_ping"] is True
    assert captured["isolation_level"] == "READ COMMITTED"
    assert captured["connect_args"] == {
        "application_name": "lot17-tests",
        "client_encoding": "UTF8",
        "options": "-c timezone=UTC",
    }
