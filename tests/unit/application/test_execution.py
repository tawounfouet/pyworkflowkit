"""Tests for explicit in-process handler registration."""

import pytest

from pyworkflowkit.application.execution import HandlerRegistry
from pyworkflowkit.errors import (
    DuplicateHandlerRegistrationError,
    HandlerNotFoundError,
)


def handler() -> str:
    return "ok"


def test_handler_registry_registers_and_resolves_handler() -> None:
    registry = HandlerRegistry()

    registry.register("tests:handler", handler)

    assert registry.resolve("tests:handler") is handler
    assert registry.contains("tests:handler")
    assert registry.handler_refs == ("tests:handler",)


def test_handler_registry_returns_sorted_references() -> None:
    registry = HandlerRegistry()
    registry.register("z:handler", handler)
    registry.register("a:handler", handler)

    assert registry.handler_refs == ("a:handler", "z:handler")


def test_handler_registry_rejects_duplicate_reference() -> None:
    registry = HandlerRegistry()
    registry.register("tests:handler", handler)

    with pytest.raises(DuplicateHandlerRegistrationError) as exc_info:
        registry.register("tests:handler", handler)

    assert exc_info.value.handler_ref == "tests:handler"


def test_handler_registry_rejects_unknown_reference() -> None:
    registry = HandlerRegistry()

    with pytest.raises(HandlerNotFoundError) as exc_info:
        registry.resolve("missing:handler")

    assert exc_info.value.handler_ref == "missing:handler"


@pytest.mark.parametrize("handler_ref", ["", " ", "\t"])
def test_handler_registry_rejects_blank_reference(handler_ref: str) -> None:
    registry = HandlerRegistry()

    with pytest.raises(ValueError, match="handler_ref"):
        registry.register(handler_ref, handler)


def test_handler_registry_rejects_non_callable() -> None:
    registry = HandlerRegistry()

    with pytest.raises(TypeError, match="callable"):
        registry.register("invalid", "not-callable")  # type: ignore[arg-type]
