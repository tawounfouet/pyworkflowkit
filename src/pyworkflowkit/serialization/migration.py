"""Explicit directed migration hooks for V2 wire envelopes."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

from pyworkflowkit.serialization.schemas import WireEnvelope

WirePayload = dict[str, object]
WireMigrator = Callable[[WirePayload], WirePayload]


class WireMigrationError(ValueError):
    """Base error for unsupported or invalid wire migration paths."""


class UnsupportedWireVersionError(WireMigrationError):
    """Raised when no explicit migration path can reach the current contract version."""


class DuplicateWireMigrationError(WireMigrationError):
    """Raised when one directed wire-migration edge is registered twice."""


class WireMigrationRegistry:
    """Directed migration graph with no implicit reverse/downgrade edges."""

    def __init__(self) -> None:
        self._migrations: dict[tuple[str, str, str], WireMigrator] = {}

    def register(
        self,
        *,
        contract: str,
        from_version: str,
        to_version: str,
        migrator: WireMigrator,
    ) -> None:
        for name, value in (
            ("contract", contract),
            ("from_version", from_version),
            ("to_version", to_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be blank")
        if from_version == to_version:
            raise ValueError("wire migration must change the contract version")
        if not callable(migrator):
            raise TypeError("migrator must be callable")

        key = (contract, from_version, to_version)
        if key in self._migrations:
            raise DuplicateWireMigrationError(
                f"wire migration {contract} {from_version}->{to_version} already exists"
            )
        self._migrations[key] = migrator

    def upgrade(
        self,
        envelope: WireEnvelope,
        *,
        target_version: str,
    ) -> WireEnvelope:
        if not isinstance(envelope, WireEnvelope):
            raise TypeError("envelope must be a WireEnvelope")
        if not isinstance(target_version, str) or not target_version.strip():
            raise ValueError("target_version must not be blank")
        if envelope.contract_version == target_version:
            return envelope

        queue: deque[tuple[str, WirePayload]] = deque(
            [(envelope.contract_version, dict(envelope.payload))]
        )
        visited = {envelope.contract_version}

        while queue:
            current_version, payload = queue.popleft()
            edges = sorted(
                (
                    to_version,
                    migrator,
                )
                for (contract, from_version, to_version), migrator in self._migrations.items()
                if contract == envelope.contract and from_version == current_version
            )
            for to_version, migrator in edges:
                if to_version in visited:
                    continue
                migrated = migrator(dict(payload))
                if not isinstance(migrated, dict):
                    raise TypeError("wire migrator must return dict[str, object]")
                if to_version == target_version:
                    return WireEnvelope(
                        contract=envelope.contract,
                        contract_version=to_version,
                        payload=migrated,
                    )
                visited.add(to_version)
                queue.append((to_version, migrated))

        raise UnsupportedWireVersionError(
            f"no explicit migration path for {envelope.contract!r} "
            f"{envelope.contract_version!r}->{target_version!r}"
        )


__all__ = [
    "DuplicateWireMigrationError",
    "UnsupportedWireVersionError",
    "WireMigrationError",
    "WireMigrationRegistry",
    "WireMigrator",
    "WirePayload",
]
