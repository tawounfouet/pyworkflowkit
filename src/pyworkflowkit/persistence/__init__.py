"""V2 persistence namespace baseline.

The 1.1 stores remain the implementation baseline while LOT-05, LOT-10 and
LOT-17 evolve the V2 persistence contract and physical schemas.
"""

from pyworkflowkit.adapters.metadata.memory import MemoryMetadataStore, MemoryUnitOfWork
from pyworkflowkit.adapters.metadata.sqlite import SQLiteMetadataStore, SQLiteSettings
from pyworkflowkit.ports.metadata_store import MetadataStore, UnitOfWork

__all__ = [
    "MemoryMetadataStore",
    "MemoryUnitOfWork",
    "MetadataStore",
    "SQLiteMetadataStore",
    "SQLiteSettings",
    "UnitOfWork",
]
