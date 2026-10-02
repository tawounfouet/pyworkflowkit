"""LOT-05 reference acceptance for canonical V2 persistence."""

from __future__ import annotations

import pyworkflowkit
import pyworkflowkit.persistence as persistence
from pyworkflowkit.adapters.metadata.memory import (
    MemoryMetadataStore as LegacyMemoryMetadataStore,
)
from pyworkflowkit.persistence import (
    InMemoryMetadataStore,
    MetadataStore,
)
from pyworkflowkit.ports.metadata_store import MetadataStore as LegacyMetadataStore


def test_v2_persistence_uses_new_contract_and_adapter() -> None:
    store = InMemoryMetadataStore()

    assert isinstance(store, MetadataStore)
    assert not isinstance(store, LegacyMetadataStore)
    assert not isinstance(store, LegacyMemoryMetadataStore)


def test_frozen_1_1_root_is_unchanged() -> None:
    assert "MetadataStore" not in pyworkflowkit.__all__
    assert "InMemoryMetadataStore" not in pyworkflowkit.__all__


def test_qualified_v2_persistence_surface_is_explicit() -> None:
    assert tuple(persistence.__all__) == (
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
        "StateEntityType",
        "StateTransitionRecord",
    )
