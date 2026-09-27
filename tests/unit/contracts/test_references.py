"""M48 unit coverage for portable reference interoperability."""

from __future__ import annotations

import pytest

from pyworkflowkit.domain.ids import ArtifactId, ExternalRunRefId
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef
from pyworkflowkit.errors import ReferenceInteroperabilityError
from pyworkflowkit.integrations import (
    REFERENCE_INTEROPERABILITY_CONTRACT_VERSION,
    normalize_reference_metadata,
    validate_portable_artifact_reference,
    validate_portable_external_run_ref,
    validate_provider_name,
    validate_reference_uri,
)


@pytest.mark.parametrize(
    "provider",
    [
        "pyingestkit",
        "acme.jobs",
        "github-actions",
        "vendor_1",
        "provider2",
    ],
)
def test_provider_names_use_stable_lowercase_identifiers(provider: str) -> None:
    assert validate_provider_name(provider) == provider


@pytest.mark.parametrize(
    "provider",
    [
        "PyIngestKit",
        "acme jobs",
        "1provider",
        "provider.",
        "provider/",
        "",
    ],
)
def test_non_portable_provider_names_are_rejected(provider: str) -> None:
    with pytest.raises(ReferenceInteroperabilityError) as caught:
        validate_provider_name(provider)

    assert caught.value.field == "provider"


@pytest.mark.parametrize(
    "uri",
    [
        "file:///tmp/output.csv",
        "s3://bucket/path/output.csv",
        "https://example.test/runs/CaseSensitive-ID",
        "urn:example:run:42",
        "memory://artifact/output",
    ],
)
def test_absolute_uri_forms_are_portable_without_normalization(uri: str) -> None:
    assert validate_reference_uri(uri, reference_kind="artifact", required=True) == uri


@pytest.mark.parametrize("uri", ["relative/path.csv", "/tmp/output.csv", "has space://bad"])
def test_non_portable_uri_is_rejected(uri: str) -> None:
    with pytest.raises(ReferenceInteroperabilityError) as caught:
        validate_reference_uri(uri, reference_kind="artifact", required=True)

    assert caught.value.field == "uri"


def test_external_reference_uri_may_be_absent() -> None:
    assert (
        validate_reference_uri(
            None,
            reference_kind="external_run",
            required=False,
        )
        is None
    )


def test_reference_metadata_is_detached_and_json_portable() -> None:
    source = {"z": (1, 2), "nested": {"ok": True}}

    normalized = normalize_reference_metadata(source, reference_kind="artifact")

    assert normalized == {"nested": {"ok": True}, "z": [1, 2]}
    assert normalized is not source


def test_non_json_portable_reference_metadata_is_rejected() -> None:
    reference = ExternalRunRef(
        external_ref_id=ExternalRunRefId("external-1"),
        provider="acme",
        external_run_id="remote-1",
        metadata={"bad": object()},
    )

    with pytest.raises(ReferenceInteroperabilityError) as caught:
        validate_portable_external_run_ref(reference)

    assert caught.value.field == "metadata"


def test_portable_validation_preserves_foreign_identity_and_uri_exactly() -> None:
    reference = ExternalRunRef(
        external_ref_id=ExternalRunRefId("external-1"),
        provider="acme.jobs",
        external_run_id="CaseSensitive/Foreign-ID:42",
        uri="https://example.test/Runs/CaseSensitive-ID?x=A",
        metadata={"region": "EU"},
    )

    validated = validate_portable_external_run_ref(reference)

    assert validated is reference
    assert validated.provider == "acme.jobs"
    assert validated.external_run_id == "CaseSensitive/Foreign-ID:42"
    assert validated.uri == "https://example.test/Runs/CaseSensitive-ID?x=A"


def test_legacy_domain_reference_can_exist_without_being_portable() -> None:
    artifact = ArtifactReference(
        artifact_id=ArtifactId("legacy"),
        name="legacy.csv",
        uri="/tmp/legacy.csv",
    )

    with pytest.raises(ReferenceInteroperabilityError):
        validate_portable_artifact_reference(artifact)


def test_reference_contract_version_is_v1() -> None:
    assert REFERENCE_INTEROPERABILITY_CONTRACT_VERSION == "1"
