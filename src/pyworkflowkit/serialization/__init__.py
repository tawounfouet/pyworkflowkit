"""V2 serialization namespace baseline.

LOT-15 introduces contract/version envelopes and dedicated V2 codecs. The current
strict schema codec remains available as migration evidence.
"""

from pyworkflowkit.contracts.serialization import SchemaCodec, StrictSchema

__all__ = ["SchemaCodec", "StrictSchema"]
