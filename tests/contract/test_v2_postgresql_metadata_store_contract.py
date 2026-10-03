"""Apply the reusable V2 MetadataStore contract to PostgreSQL."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from pyworkflowkit.errors import MetadataConflictError
from pyworkflowkit.migrations import MIGRATION_HEAD_REVISION
from pyworkflowkit.persistence import (
    MetadataStore,
    PostgreSQLMetadataStore,
)
from pyworkflowkit.states import WorkflowRunStateMachine, WorkflowRunStatus

from .v2_metadata_store_conformance import (
    T1,
    T2,
    MetadataStoreContractSuite,
    workflow_run,
)

POSTGRES_DSN = os.environ.get("PYWORKFLOWKIT_TEST_POSTGRES_DSN")

pytestmark = pytest.mark.skipif(
    POSTGRES_DSN is None,
    reason="PYWORKFLOWKIT_TEST_POSTGRES_DSN is not configured",
)


def _dsn() -> str:
    if POSTGRES_DSN is None:
        raise RuntimeError("PYWORKFLOWKIT_TEST_POSTGRES_DSN is not configured")
    return POSTGRES_DSN


def _clear_v2_runtime_tables(store: PostgreSQLMetadataStore) -> None:
    with store.engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    pyworkflowkit.v2_state_transitions,
                    pyworkflowkit.v2_workflow_runs
                RESTART IDENTITY CASCADE
                """
            )
        )


class TestPostgreSQLMetadataStoreContract(MetadataStoreContractSuite):
    store: PostgreSQLMetadataStore

    @pytest.fixture(autouse=True)
    def _postgresql_store(self):
        self.store = PostgreSQLMetadataStore(_dsn())
        _clear_v2_runtime_tables(self.store)
        yield
        self.store.close()

    def test_store_reports_server_durable_schema_identity(self) -> None:
        assert isinstance(self.store, MetadataStore)

        metadata = self.store.metadata()

        assert metadata.durable is True
        assert metadata.schema_version == MIGRATION_HEAD_REVISION
        assert metadata.supports_concurrent_writers is True
        assert metadata.supports_atomic_batch is False


def test_lot17_two_store_instances_reject_stale_compare_and_set() -> None:
    with (
        PostgreSQLMetadataStore(_dsn()) as first_store,
        PostgreSQLMetadataStore(_dsn(), create_schema=False) as second_store,
    ):
        _clear_v2_runtime_tables(first_store)

        run = workflow_run()
        first_store.create_workflow_run(run)

        first_view = first_store.get_workflow_run(run.run_id)
        stale_view = second_store.get_workflow_run(run.run_id)

        WorkflowRunStateMachine().transition(
            first_view,
            WorkflowRunStatus.RUNNING,
            at=T1,
        )
        first_store.update_workflow_run(
            first_view,
            expected_status=WorkflowRunStatus.PENDING,
            transitioned_at=T1,
        )

        WorkflowRunStateMachine().transition(
            stale_view,
            WorkflowRunStatus.RUNNING,
            at=T2,
        )
        with pytest.raises(MetadataConflictError):
            second_store.update_workflow_run(
                stale_view,
                expected_status=WorkflowRunStatus.PENDING,
                transitioned_at=T2,
            )


def test_lot17_postgresql_session_contract_is_read_committed_utf8_and_utc() -> None:
    with PostgreSQLMetadataStore(_dsn()) as store, store.engine.connect() as connection:
        isolation = connection.execute(text("SHOW transaction_isolation")).scalar_one()
        timezone = connection.execute(text("SHOW timezone")).scalar_one()
        encoding = connection.execute(text("SHOW client_encoding")).scalar_one()
        application_name = connection.execute(text("SHOW application_name")).scalar_one()

    assert str(isolation).lower() == "read committed"
    assert str(timezone).upper() == "UTC"
    assert str(encoding).upper() == "UTF8"
    assert application_name == "pyworkflowkit-v2"
