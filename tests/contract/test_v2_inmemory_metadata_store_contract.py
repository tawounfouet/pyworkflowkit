"""Apply the reusable V2 MetadataStore suite to the in-memory adapter."""

from pyworkflowkit.persistence.memory import InMemoryMetadataStore

from .v2_metadata_store_conformance import MetadataStoreContractSuite


class TestInMemoryMetadataStoreContract(MetadataStoreContractSuite):
    def setup_method(self) -> None:
        self.store = InMemoryMetadataStore()
