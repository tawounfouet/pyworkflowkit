"""Handler registration and lookup for workload execution."""

from pyworkflowkit.domain.ids import validate_non_empty_identifier
from pyworkflowkit.errors import (
    DuplicateHandlerRegistrationError,
    HandlerNotFoundError,
)
from pyworkflowkit.ports.executor import TaskHandler


class HandlerRegistry:
    """Explicit in-process mapping between handler references and callables."""

    def __init__(self) -> None:
        self._handlers: dict[str, TaskHandler] = {}

    def register(self, handler_ref: str, handler: TaskHandler) -> None:
        validate_non_empty_identifier(handler_ref, field_name="handler_ref")
        if not callable(handler):
            raise TypeError("handler must be callable.")
        if handler_ref in self._handlers:
            raise DuplicateHandlerRegistrationError(handler_ref=handler_ref)
        self._handlers[handler_ref] = handler

    def resolve(self, handler_ref: str) -> TaskHandler:
        validate_non_empty_identifier(handler_ref, field_name="handler_ref")
        try:
            return self._handlers[handler_ref]
        except KeyError as exc:
            raise HandlerNotFoundError(handler_ref=handler_ref) from exc

    def contains(self, handler_ref: str) -> bool:
        return handler_ref in self._handlers

    @property
    def handler_refs(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))


__all__ = ["HandlerRegistry"]
