"""Compatibility and deprecation contracts for PyWorkflowKit."""

from __future__ import annotations

import re
import warnings
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from functools import wraps
from typing import ParamSpec, TypeVar

MINIMUM_DEPRECATION_MINOR_LINES = 1
_VERSION_LINE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)(?:\.|$)")


class DeprecationKind(StrEnum):
    API = "api"
    CLI = "cli"
    CONFIGURATION = "configuration"
    PLUGIN = "plugin"
    PERSISTENCE = "persistence"


class PyWorkflowKitDeprecationWarning(FutureWarning):
    def __init__(self, spec: DeprecationSpec) -> None:
        self.spec = spec
        super().__init__(spec.message)


class PyWorkflowKitAPIDeprecationWarning(PyWorkflowKitDeprecationWarning):
    pass


class PyWorkflowKitCLIDeprecationWarning(PyWorkflowKitDeprecationWarning):
    pass


class PyWorkflowKitConfigurationDeprecationWarning(PyWorkflowKitDeprecationWarning):
    pass


class PyWorkflowKitPluginDeprecationWarning(PyWorkflowKitDeprecationWarning):
    pass


class PyWorkflowKitPersistenceDeprecationWarning(PyWorkflowKitDeprecationWarning):
    pass


_WARNING_TYPES: dict[DeprecationKind, type[PyWorkflowKitDeprecationWarning]] = {
    DeprecationKind.API: PyWorkflowKitAPIDeprecationWarning,
    DeprecationKind.CLI: PyWorkflowKitCLIDeprecationWarning,
    DeprecationKind.CONFIGURATION: PyWorkflowKitConfigurationDeprecationWarning,
    DeprecationKind.PLUGIN: PyWorkflowKitPluginDeprecationWarning,
    DeprecationKind.PERSISTENCE: PyWorkflowKitPersistenceDeprecationWarning,
}


@dataclass(frozen=True, slots=True)
class DeprecationSpec:
    subject: str
    kind: DeprecationKind
    since: str
    removal: str
    replacement: str | None = None
    reason: str | None = None
    emergency: bool = False

    def __post_init__(self) -> None:
        _require_text(self.subject, field_name="subject")
        if not isinstance(self.kind, DeprecationKind):
            raise TypeError("kind must be a DeprecationKind")
        _require_text(self.since, field_name="since")
        _require_text(self.removal, field_name="removal")
        if self.replacement is not None:
            _require_text(self.replacement, field_name="replacement")
        if self.reason is not None:
            _require_text(self.reason, field_name="reason")
        if self.emergency and self.reason is None:
            raise ValueError("emergency deprecation requires a concrete reason")

        if not self.emergency and not _is_later_release_line(
            since=_release_line(self.since),
            removal=_release_line(self.removal),
        ):
            raise ValueError(
                "normal deprecation removal must target at least the next minor release line"
            )

    @property
    def message(self) -> str:
        parts = [
            (
                f"{self.subject} is deprecated since {self.since} and is planned "
                f"for removal in {self.removal}."
            )
        ]
        if self.replacement is not None:
            parts.append(f"Use {self.replacement} instead.")
        if self.reason is not None:
            parts.append(f"{self.reason.rstrip('.')}.")
        if self.emergency:
            parts.append("This deprecation uses the documented emergency compatibility exception.")
        return " ".join(parts)

    @property
    def warning_type(self) -> type[PyWorkflowKitDeprecationWarning]:
        return _WARNING_TYPES[self.kind]

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (self.kind.value, self.subject, self.since, self.removal)


class DeprecationEmitter:
    def __init__(self) -> None:
        self._emitted: set[tuple[str, str, str, str]] = set()

    def warn(self, spec: DeprecationSpec, *, stacklevel: int = 2) -> bool:
        if stacklevel < 1:
            raise ValueError("stacklevel must be greater than or equal to 1")
        if spec.identity in self._emitted:
            return False
        warnings.warn(spec.warning_type(spec), stacklevel=stacklevel)
        self._emitted.add(spec.identity)
        return True

    @property
    def emitted_identities(self) -> frozenset[tuple[str, str, str, str]]:
        return frozenset(self._emitted)


_DEFAULT_EMITTER = DeprecationEmitter()


def warn_deprecated(spec: DeprecationSpec, *, stacklevel: int = 2) -> bool:
    return _DEFAULT_EMITTER.warn(spec, stacklevel=stacklevel + 1)


P = ParamSpec("P")
R = TypeVar("R")


def deprecated(
    spec: DeprecationSpec,
    *,
    emitter: DeprecationEmitter | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    selected_emitter = emitter if emitter is not None else _DEFAULT_EMITTER

    def decorator(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            selected_emitter.warn(spec, stacklevel=3)
            return function(*args, **kwargs)

        return wrapper

    return decorator


def validate_deprecation_catalog(specs: Iterable[DeprecationSpec]) -> tuple[DeprecationSpec, ...]:
    values = tuple(specs)
    seen: set[tuple[DeprecationKind, str]] = set()
    for spec in values:
        key = (spec.kind, spec.subject)
        if key in seen:
            raise ValueError(f"duplicate active deprecation for {spec.kind.value}:{spec.subject}")
        seen.add(key)
    return tuple(sorted(values, key=lambda spec: (spec.kind.value, spec.subject)))


ACTIVE_DEPRECATIONS: tuple[DeprecationSpec, ...] = validate_deprecation_catalog(())


def _require_text(value: str, *, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _release_line(value: str) -> tuple[int, int]:
    match = _VERSION_LINE.match(value)
    if match is None:
        raise ValueError(f"version '{value}' must start with a numeric major.minor release line")
    return (int(match.group("major")), int(match.group("minor")))


def _is_later_release_line(
    *,
    since: tuple[int, int],
    removal: tuple[int, int],
) -> bool:
    since_major, since_minor = since
    removal_major, removal_minor = removal
    if removal_major > since_major:
        return True
    if removal_major < since_major:
        return False
    return removal_minor >= since_minor + MINIMUM_DEPRECATION_MINOR_LINES


__all__ = [
    "ACTIVE_DEPRECATIONS",
    "MINIMUM_DEPRECATION_MINOR_LINES",
    "DeprecationEmitter",
    "DeprecationKind",
    "DeprecationSpec",
    "PyWorkflowKitAPIDeprecationWarning",
    "PyWorkflowKitCLIDeprecationWarning",
    "PyWorkflowKitConfigurationDeprecationWarning",
    "PyWorkflowKitDeprecationWarning",
    "PyWorkflowKitPersistenceDeprecationWarning",
    "PyWorkflowKitPluginDeprecationWarning",
    "deprecated",
    "validate_deprecation_catalog",
    "warn_deprecated",
]
