"""Portable artifact and external-run reference interoperability contract."""

from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import urlsplit

from pyworkflowkit.contracts.serialization import normalize_portable_json_value
from pyworkflowkit.domain.values import ArtifactReference, ExternalRunRef
from pyworkflowkit.errors import ReferenceInteroperabilityError, SerializationError

REFERENCE_INTEROPERABILITY_CONTRACT_VERSION = "1"

_PROVIDER_NAME_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


def validate_provider_name(provider: str) -> str:
    """Validate one stable provider identifier without rewriting it."""

    if not isinstance(provider, str):
        raise ReferenceInteroperabilityError(
            reference_kind="external_run",
            field="provider",
            reason="provider must be a string",
        )
    if not _PROVIDER_NAME_RE.fullmatch(provider):
        raise ReferenceInteroperabilityError(
            reference_kind="external_run",
            field="provider",
            reason=(
                "provider must be a lowercase stable identifier using letters, digits, "
                "'.', '_' or '-' separators"
            ),
        )
    return provider


def validate_reference_uri(
    uri: str | None,
    *,
    reference_kind: str,
    required: bool,
) -> str | None:
    """Validate a portable absolute URI without normalizing its spelling."""

    if uri is None:
        if required:
            raise ReferenceInteroperabilityError(
                reference_kind=reference_kind,
                field="uri",
                reason="uri is required",
            )
        return None
    if not isinstance(uri, str) or not uri.strip():
        raise ReferenceInteroperabilityError(
            reference_kind=reference_kind,
            field="uri",
            reason="uri must be a non-empty string",
        )
    if any(character.isspace() for character in uri):
        raise ReferenceInteroperabilityError(
            reference_kind=reference_kind,
            field="uri",
            reason="uri must not contain whitespace",
        )
    parsed = urlsplit(uri)
    if not parsed.scheme:
        raise ReferenceInteroperabilityError(
            reference_kind=reference_kind,
            field="uri",
            reason="portable references require an absolute URI with a scheme",
        )
    return uri


def normalize_reference_metadata(
    metadata: Mapping[str, object],
    *,
    reference_kind: str,
) -> dict[str, object]:
    """Return detached deterministic JSON-portable metadata."""

    try:
        normalized = normalize_portable_json_value(
            metadata,
            path=f"{reference_kind}.metadata",
        )
    except SerializationError as exc:
        raise ReferenceInteroperabilityError(
            reference_kind=reference_kind,
            field="metadata",
            reason=str(exc),
        ) from exc
    if not isinstance(normalized, dict):
        raise TypeError("reference metadata normalization must return a dict")
    return normalized


def validate_portable_artifact_reference(value: ArtifactReference) -> ArtifactReference:
    """Assert ArtifactReference portability without changing its identity."""

    validate_reference_uri(
        value.uri,
        reference_kind="artifact",
        required=True,
    )
    normalize_reference_metadata(value.metadata, reference_kind="artifact")
    return value


def validate_portable_external_run_ref(value: ExternalRunRef) -> ExternalRunRef:
    """Assert ExternalRunRef portability without changing foreign identifiers."""

    validate_provider_name(value.provider)
    validate_reference_uri(
        value.uri,
        reference_kind="external_run",
        required=False,
    )
    normalize_reference_metadata(value.metadata, reference_kind="external_run")
    return value


__all__ = [
    "REFERENCE_INTEROPERABILITY_CONTRACT_VERSION",
    "normalize_reference_metadata",
    "validate_portable_artifact_reference",
    "validate_portable_external_run_ref",
    "validate_provider_name",
    "validate_reference_uri",
]
