"""Pre-freeze wire-contract descriptors for V2 portable boundary values.

LOT-01 records contract identities and versions. LOT-15 owns the final codecs,
golden fixtures, migration hooks and durable decoding rules.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class WireContractDescriptor:
    """Stable identity for a portable contract family."""

    contract: str
    contract_version: str
    owner: str

    def __post_init__(self) -> None:
        for name, value in (
            ("contract", self.contract),
            ("contract_version", self.contract_version),
            ("owner", self.owner),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")


V2_BOUNDARY_WIRE_CONTRACTS: Mapping[str, WireContractDescriptor] = MappingProxyType(
    {
        "correlation_context": WireContractDescriptor(
            contract="pykit.correlation_context",
            contract_version="1",
            owner="pykit",
        ),
        "diagnostic": WireContractDescriptor(
            contract="pyworkflowkit.diagnostic",
            contract_version="1",
            owner="pyworkflowkit",
        ),
        "external_run_ref": WireContractDescriptor(
            contract="pyworkflowkit.external_run_ref",
            contract_version="1",
            owner="pyworkflowkit",
        ),
        "failure_evidence": WireContractDescriptor(
            contract="pykit.failure_evidence",
            contract_version="1",
            owner="pykit",
        ),
        "workflow_execution_reference": WireContractDescriptor(
            contract="pyworkflowkit.workflow_execution_reference",
            contract_version="1",
            owner="pyworkflowkit",
        ),
    }
)


def v2_boundary_wire_contract_snapshot() -> dict[str, object]:
    """Return deterministic JSON-serializable LOT-01 contract metadata."""

    return {
        "contract_family_version": "1",
        "contracts": {
            name: {
                "contract": descriptor.contract,
                "contract_version": descriptor.contract_version,
                "owner": descriptor.owner,
            }
            for name, descriptor in sorted(V2_BOUNDARY_WIRE_CONTRACTS.items())
        },
    }


__all__ = [
    "V2_BOUNDARY_WIRE_CONTRACTS",
    "WireContractDescriptor",
    "v2_boundary_wire_contract_snapshot",
]
