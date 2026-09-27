"""M45 reference acceptance for persistence and migration compatibility."""

from __future__ import annotations

import hashlib
from importlib.resources import files

from alembic.script import ScriptDirectory

from pyworkflowkit.migrations import (
    MIGRATION_HEAD_REVISION,
    MIGRATION_HISTORY,
    PERSISTENCE_SCHEMA_CONTRACT_VERSION,
    SUPPORTED_UPGRADE_ORIGINS,
)
from pyworkflowkit.migrations.runner import alembic_config

EXPECTED_MIGRATION_GIT_BLOBS = {
    "0001_runtime_metadata.py": "bb0cdfdc9ead5a34ac96cf4a6ce8e18a20aa22e6",
    "0002_task_output_checkpoints.py": "9978fac4fa49ef459cb8fd468119b1f8554e8170",
    "0003_retry_eligible_at.py": "6b11ec24d588a448c2547b3c129218d3d51f36c2",
}


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def test_m45_persistence_contract_and_migration_lineage_are_frozen() -> None:
    assert PERSISTENCE_SCHEMA_CONTRACT_VERSION == "1"
    assert MIGRATION_HISTORY == (
        "0001_runtime_metadata",
        "0002_task_output_checkpoints",
        "0003_retry_eligible_at",
    )
    assert MIGRATION_HEAD_REVISION == "0003_retry_eligible_at"
    assert SUPPORTED_UPGRADE_ORIGINS == frozenset(MIGRATION_HISTORY)

    script = ScriptDirectory.from_config(alembic_config())
    packaged = tuple(revision.revision for revision in reversed(tuple(script.walk_revisions())))

    assert packaged == MIGRATION_HISTORY
    assert script.get_current_head() == MIGRATION_HEAD_REVISION


def test_m45_published_migration_sources_are_immutable() -> None:
    versions = files("pyworkflowkit.migrations.versions")

    actual = {
        filename: _git_blob_sha(versions.joinpath(filename).read_bytes())
        for filename in EXPECTED_MIGRATION_GIT_BLOBS
    }

    assert actual == EXPECTED_MIGRATION_GIT_BLOBS
