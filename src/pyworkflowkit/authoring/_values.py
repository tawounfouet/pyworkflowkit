"""Internal helpers for immutable authoring values."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isfinite
from types import MappingProxyType
from typing import TypeAlias

JsonScalar: TypeAlias = str | int | float | bool | None
FrozenJsonValue: TypeAlias = (
    JsonScalar | tuple["FrozenJsonValue", ...] | Mapping[str, "FrozenJsonValue"]
)


def require_non_empty_text(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def freeze_metadata(metadata: Mapping[str, object]) -> Mapping[str, FrozenJsonValue]:
    """Deep-freeze JSON-like authoring metadata."""

    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a mapping")

    frozen: dict[str, FrozenJsonValue] = {}
    for key, value in metadata.items():
        require_non_empty_text(key, field_name="metadata key")
        frozen[key] = freeze_json_value(value, path=f"metadata.{key}")
    return MappingProxyType(frozen)


def freeze_json_value(value: object, *, path: str) -> FrozenJsonValue:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"{path} must contain only finite numbers")
        return value
    if isinstance(value, Mapping):
        nested: dict[str, FrozenJsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError(f"{path} mapping keys must be non-empty strings")
            nested[key] = freeze_json_value(item, path=f"{path}.{key}")
        return MappingProxyType(nested)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(
            freeze_json_value(item, path=f"{path}[{index}]") for index, item in enumerate(value)
        )
    raise TypeError(
        f"{path} must contain only JSON-like immutable authoring values; got {type(value).__name__}"
    )


def thaw_json_value(value: FrozenJsonValue) -> object:
    """Convert a frozen authoring value into canonical JSON-compatible data."""

    if isinstance(value, Mapping):
        return {key: thaw_json_value(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [thaw_json_value(item) for item in value]
    return value


__all__ = [
    "FrozenJsonValue",
    "JsonScalar",
    "freeze_json_value",
    "freeze_metadata",
    "require_non_empty_text",
    "thaw_json_value",
]
