"""M48 reference acceptance for portable integration evidence."""

from __future__ import annotations

from pathlib import Path

from pyworkflowkit._compat.v1_root import TaskResult, WorkflowRuntime, task, workflow
from pyworkflowkit.adapters.metadata.sqlite import SQLiteMetadataStore
from pyworkflowkit.application.manifest import RunManifestSerializer
from pyworkflowkit.application.mapping import DomainSchemaMapper
from pyworkflowkit.config import MetadataSettings, RuntimeSettings
from pyworkflowkit.contracts.serialization import (
    ArtifactReferenceSchema,
    ExternalRunRefSchema,
    SchemaCodec,
)
from pyworkflowkit.domain.ids import ArtifactId, ExternalRunRefId, TaskRunId
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef
from pyworkflowkit.integrations import (
    REFERENCE_INTEROPERABILITY_CONTRACT_VERSION,
    validate_portable_artifact_reference,
    validate_portable_external_run_ref,
)


def test_reference_round_trip_preserves_identity_uri_and_portable_metadata() -> None:
    artifact = ArtifactReference(
        artifact_id=ArtifactId("artifact:CaseSensitive-1"),
        name="Output.CSV",
        uri="s3://Bucket-Case/Path/Output.CSV",
        media_type="text/csv",
        checksum="sha256:ABCDEF",
        size_bytes=42,
        metadata={"rows": 3, "labels": ["A", "B"]},
    )
    external = ExternalRunRef(
        external_ref_id=ExternalRunRefId("external:1"),
        provider="acme.jobs",
        external_run_id="CaseSensitive/Foreign-ID:42",
        uri="https://example.test/Runs/CaseSensitive-ID?x=A",
        metadata={"region": "EU", "attempts": 2},
    )

    validate_portable_artifact_reference(artifact)
    validate_portable_external_run_ref(external)

    artifact_json = SchemaCodec.to_json(DomainSchemaMapper.artifact_to_schema(artifact))
    external_json = SchemaCodec.to_json(DomainSchemaMapper.external_ref_to_schema(external))

    restored_artifact = DomainSchemaMapper.artifact_from_schema(
        SchemaCodec.from_json(ArtifactReferenceSchema, artifact_json)
    )
    restored_external = DomainSchemaMapper.external_ref_from_schema(
        SchemaCodec.from_json(ExternalRunRefSchema, external_json)
    )

    assert restored_artifact == artifact
    assert restored_external == external
    assert restored_external.external_run_id == "CaseSensitive/Foreign-ID:42"
    assert restored_external.uri == "https://example.test/Runs/CaseSensitive-ID?x=A"


def test_durable_evidence_redacts_manifest_and_sorts_lineage(tmp_path: Path) -> None:
    database = tmp_path / "m48.sqlite3"
    settings = RuntimeSettings(
        metadata=MetadataSettings(
            backend="sqlite",
            sqlite_path=database,
            sqlite_wal=False,
        )
    )

    z_artifact = ArtifactReference(
        artifact_id=ArtifactId("z-artifact"),
        name="z.csv",
        uri="s3://bucket/z.csv",
        metadata={
            "api_token": "artifact-secret",
            "nested": {"password": "nested-artifact-secret", "safe": 1},
        },
    )
    a_artifact = ArtifactReference(
        artifact_id=ArtifactId("a-artifact"),
        name="a.csv",
        uri="s3://bucket/a.csv",
        metadata={"safe": "artifact"},
    )
    z_external = ExternalRunRef(
        external_ref_id=ExternalRunRefId("z-external"),
        provider="acme.jobs",
        external_run_id="Remote/Z",
        uri="https://example.test/runs/Z",
        metadata={
            "authorization": "Bearer external-secret",
            "nested": {"private_key": "external-key", "safe": 2},
        },
    )
    a_external = ExternalRunRef(
        external_ref_id=ExternalRunRefId("a-external"),
        provider="vendor_1",
        external_run_id="Remote/A",
        uri="urn:vendor:run:A",
        metadata={"safe": "external"},
    )

    for artifact in (z_artifact, a_artifact):
        validate_portable_artifact_reference(artifact)
    for external in (z_external, a_external):
        validate_portable_external_run_ref(external)

    @task(id="produce")
    def produce() -> TaskResult:
        return TaskResult(
            output="done",
            artifacts=(z_artifact, a_artifact),
            external_refs=(z_external, a_external),
        )

    @workflow(id="reference.m48", version="1")
    def definition():
        return (produce,)

    runtime = WorkflowRuntime(settings)
    runtime.register(produce.handler_ref, produce.handler)
    workflow_definition = definition.build()
    run = runtime.run(workflow_definition)

    manifest = runtime.manifest(workflow_definition, run.run_id)
    lineage = runtime.lineage(workflow_definition, run.run_id)
    serialized = RunManifestSerializer().to_json(manifest)

    task_manifest = manifest.tasks[0]
    assert tuple(value.artifact_id for value in task_manifest.artifacts) == (
        "a-artifact",
        "z-artifact",
    )
    assert tuple(value.external_ref_id for value in task_manifest.external_refs) == (
        "a-external",
        "z-external",
    )
    assert task_manifest.external_refs[1].provider == "acme.jobs"
    assert task_manifest.external_refs[1].external_run_id == "Remote/Z"
    assert task_manifest.external_refs[1].uri == "https://example.test/runs/Z"
    assert task_manifest.artifacts[1].metadata["api_token"] == "<redacted>"
    assert task_manifest.artifacts[1].metadata["nested"] == {
        "password": "<redacted>",
        "safe": 1,
    }
    assert task_manifest.external_refs[1].metadata["authorization"] == "<redacted>"
    assert task_manifest.external_refs[1].metadata["nested"] == {
        "private_key": "<redacted>",
        "safe": 2,
    }
    assert "artifact-secret" not in serialized
    assert "nested-artifact-secret" not in serialized
    assert "external-secret" not in serialized
    assert "external-key" not in serialized

    task_lineage = lineage.tasks[0]
    assert task_lineage.artifact_ids == ("a-artifact", "z-artifact")
    assert task_lineage.external_ref_ids == ("a-external", "z-external")

    with SQLiteMetadataStore(database, wal=False, create_schema=False) as store:
        task_run_id = TaskRunId(task_manifest.task_run_id)
        stored_artifacts = tuple(
            sorted(store.list_artifacts(task_run_id), key=lambda item: str(item.artifact_id))
        )
        stored_external = tuple(
            sorted(
                store.list_external_run_refs(task_run_id),
                key=lambda item: str(item.external_ref_id),
            )
        )

    assert stored_artifacts[1].uri == "s3://bucket/z.csv"
    assert stored_artifacts[1].metadata["api_token"] == "artifact-secret"
    assert stored_external[1].external_run_id == "Remote/Z"
    assert stored_external[1].uri == "https://example.test/runs/Z"
    assert stored_external[1].metadata["authorization"] == "Bearer external-secret"
    assert REFERENCE_INTEROPERABILITY_CONTRACT_VERSION == "1"
