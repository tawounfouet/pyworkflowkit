"""V2 serialization namespace baseline.

LOT-01 freezes portable boundary contract identities. LOT-15 introduces the
final versioned codecs and golden wire fixtures.
"""

from pyworkflowkit.contracts.serialization import SchemaCodec, StrictSchema
from pyworkflowkit.serialization.contracts import (
    V2_BOUNDARY_WIRE_CONTRACTS,
    WireContractDescriptor,
    v2_boundary_wire_contract_snapshot,
)

__all__ = [
    "SchemaCodec",
    "StrictSchema",
    "V2_BOUNDARY_WIRE_CONTRACTS",
    "WireContractDescriptor",
    "v2_boundary_wire_contract_snapshot",
]
