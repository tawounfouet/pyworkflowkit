"""Immutable task input/output declaration values."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pyworkflowkit.authoring._values import (
    FrozenJsonValue,
    freeze_metadata,
    require_non_empty_text,
)


@dataclass(frozen=True, slots=True)
class InputDeclaration:
    """Runtime-independent declaration of one named task input."""

    name: str
    required: bool = True
    portable: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.name, field_name="input name")
        if not isinstance(self.required, bool):
            raise TypeError("required must be a bool")
        if not isinstance(self.portable, bool):
            raise TypeError("portable must be a bool")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "portable": self.portable,
            "required": self.required,
            "metadata": _metadata_payload(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class OutputDeclaration:
    """Runtime-independent declaration of one named task output."""

    name: str
    portable: bool = True
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.name, field_name="output name")
        if not isinstance(self.portable, bool):
            raise TypeError("portable must be a bool")
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def fingerprint_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "portable": self.portable,
            "metadata": _metadata_payload(self.metadata),
        }


def _metadata_payload(metadata: Mapping[str, FrozenJsonValue]) -> dict[str, object]:
    from pyworkflowkit.authoring._values import thaw_json_value

    return {
        key: thaw_json_value(metadata[key])
        for key in sorted(metadata)
    }


__all__ = ["InputDeclaration", "OutputDeclaration"]
