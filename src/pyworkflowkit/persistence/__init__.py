"""Canonical PyWorkflowKit V2 persistence surface.

Legacy 1.1 stores remain available through explicit Legacy* aliases during migration.
"""

from pyworkflowkit.adapters.metadata.memory import (
    MemoryMetadataStore as LegacyMemoryMetadataStore,
)
from pyworkflowkit.adapters.metadata.memory import MemoryUnitOfWork as LegacyMemoryUnitOfWork
from pyworkflowkit.adapters.metadata.sqlite import (
    SQLiteMetadataStore as LegacySQLiteMetadataStore,
)
from pyworkflowkit.adapters.metadata.sqlite import SQLiteSettings as LegacySQLiteSettings
from pyworkflowkit.persistence.contracts import (
    V2_METADATA_STORE_CONTRACT_VERSION,
    V2_METADATA_STORE_METHODS,
    ManifestReference,
    MetadataStore,
    MetadataStoreMetadata,
    StateEntityType,
    StateTransitionRecord,
    v2_metadata_store_contract_snapshot,
)
from pyworkflowkit.persistence.memory import InMemoryMetadataStore
from pyworkflowkit.persistence.sqlite import SQLiteMetadataStore, SQLiteSettings
from pyworkflowkit.ports.metadata_store import MetadataStore as LegacyMetadataStore
from pyworkflowkit.ports.metadata_store import UnitOfWork as LegacyUnitOfWork

__all__ = [
    "InMemoryMetadataStore",
    "LegacyMemoryMetadataStore",
    "LegacyMemoryUnitOfWork",
    "LegacyMetadataStore",
    "LegacySQLiteMetadataStore",
    "LegacySQLiteSettings",
    "LegacyUnitOfWork",
    "ManifestReference",
    "MetadataStore",
    "MetadataStoreMetadata",
    "SQLiteMetadataStore",
    "SQLiteSettings",
    "StateEntityType",
    "StateTransitionRecord",
    "V2_METADATA_STORE_CONTRACT_VERSION",
    "V2_METADATA_STORE_METHODS",
    "v2_metadata_store_contract_snapshot",
]
