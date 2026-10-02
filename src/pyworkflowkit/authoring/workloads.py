"""Canonical workload declarations for V2 task authoring."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeAlias, runtime_checkable

from pyworkflowkit.authoring._values import require_non_empty_text


class WorkloadPortability(StrEnum):
    LOCAL_ONLY = "local_only"
    PORTABLE = "portable"


@runtime_checkable
class WorkloadDescriptor(Protocol):
    """Protocol implemented by schema-driven portable workload descriptors."""

    @property
    def workload_kind(self) -> str:
        """Stable workload category."""

    @property
    def portability(self) -> WorkloadPortability:
        """Whether the descriptor is safe to persist for later reconstruction."""

    def fingerprint_payload(self) -> Mapping[str, object]:
        """Return deterministic semantic payload for definition fingerprinting."""


@dataclass(frozen=True, slots=True)
class RegisteredWorkload:
    """Portable reference to workload code resolved through an explicit registry."""

    registry_key: str
    parameters: tuple[tuple[str, str], ...] = ()
    executor_key: str | None = None
    contract_version: str = "1"

    def __post_init__(self) -> None:
        require_non_empty_text(self.registry_key, field_name="registry_key")
        if self.executor_key is not None:
            require_non_empty_text(self.executor_key, field_name="executor_key")
        require_non_empty_text(self.contract_version, field_name="contract_version")

        parameters = tuple(self.parameters)
        seen: set[str] = set()
        for item in parameters:
            if (
                not isinstance(item, tuple)
                or len(item) != 2
                or not all(isinstance(value, str) for value in item)
            ):
                raise TypeError("parameters must contain string key/value pairs")
            key, _ = item
            require_non_empty_text(key, field_name="parameter key")
            if key in seen:
                raise ValueError(f"duplicate workload parameter {key!r}")
            seen.add(key)
        object.__setattr__(
            self,
            "parameters",
            tuple(sorted(parameters, key=lambda item: item[0])),
        )

    @property
    def workload_kind(self) -> str:
        return "registered"

    @property
    def portability(self) -> WorkloadPortability:
        return WorkloadPortability.PORTABLE

    def fingerprint_payload(self) -> Mapping[str, object]:
        return {
            "kind": self.workload_kind,
            "registry_key": self.registry_key,
            "parameters": [list(item) for item in self.parameters],
            "executor_key": self.executor_key,
            "contract_version": self.contract_version,
        }


LocalCallable: TypeAlias = Callable[..., object]
Workload: TypeAlias = LocalCallable | WorkloadDescriptor


def workload_portability(workload: Workload) -> WorkloadPortability:
    if isinstance(workload, WorkloadDescriptor):
        return workload.portability
    if callable(workload):
        return WorkloadPortability.LOCAL_ONLY
    raise TypeError("workload must be callable or implement WorkloadDescriptor")


def workload_fingerprint_payload(workload: Workload) -> Mapping[str, object]:
    """Return deterministic workload identity without executing workload code."""

    if isinstance(workload, WorkloadDescriptor):
        payload = workload.fingerprint_payload()
        if not isinstance(payload, Mapping):
            raise TypeError("fingerprint_payload() must return a mapping")
        return payload

    if callable(workload):
        module = getattr(workload, "__module__", None)
        qualname = getattr(workload, "__qualname__", None)
        if not isinstance(module, str) or not module.strip():
            raise ValueError(
                "local callable workload must expose __module__ for deterministic fingerprinting"
            )
        if not isinstance(qualname, str) or not qualname.strip():
            raise ValueError(
                "local callable workload must expose __qualname__; "
                "use RegisteredWorkload for callable objects"
            )
        return {
            "kind": "python_callable",
            "callable_ref": f"{module}:{qualname}",
            "portability": WorkloadPortability.LOCAL_ONLY.value,
        }

    raise TypeError("workload must be callable or implement WorkloadDescriptor")


__all__ = [
    "LocalCallable",
    "RegisteredWorkload",
    "Workload",
    "WorkloadDescriptor",
    "WorkloadPortability",
    "workload_fingerprint_payload",
    "workload_portability",
]
