"""Canonical V2 serialization contracts and codecs."""

from pyworkflowkit.serialization.codec import (
    DEFAULT_MAX_NESTING_DEPTH,
    DEFAULT_MAX_PAYLOAD_BYTES,
    BoundaryContractSpec,
    BoundaryUpcasterRegistry,
    BoundaryWireCodec,
    WireContractError,
    boundary_contract_specs,
)
from pyworkflowkit.serialization.contracts import (
    V2_BOUNDARY_WIRE_CONTRACTS,
    WireContractDescriptor,
    v2_boundary_wire_contract_snapshot,
)
from pyworkflowkit.serialization.mapping import BoundaryValue
from pyworkflowkit.serialization.schemas import (
    CorrelationContextSchema,
    DiagnosticSchema,
    ExternalRunRefSchema,
    FailureEvidenceSchema,
    StrictBoundarySchema,
    WireEnvelopeSchema,
    WorkflowExecutionReferenceSchema,
)

# Transitional qualified aliases now point at the V2 implementation. The frozen
# pyworkflowkit.contracts.serialization module remains the 1.1 codec surface.
SchemaCodec = BoundaryWireCodec
StrictSchema = StrictBoundarySchema

__all__ = [
    "BoundaryContractSpec",
    "BoundaryUpcasterRegistry",
    "BoundaryValue",
    "BoundaryWireCodec",
    "CorrelationContextSchema",
    "DEFAULT_MAX_NESTING_DEPTH",
    "DEFAULT_MAX_PAYLOAD_BYTES",
    "DiagnosticSchema",
    "ExternalRunRefSchema",
    "FailureEvidenceSchema",
    "SchemaCodec",
    "StrictBoundarySchema",
    "StrictSchema",
    "V2_BOUNDARY_WIRE_CONTRACTS",
    "WireContractDescriptor",
    "WireContractError",
    "WireEnvelopeSchema",
    "WorkflowExecutionReferenceSchema",
    "boundary_contract_specs",
    "v2_boundary_wire_contract_snapshot",
]
