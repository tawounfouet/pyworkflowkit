"""Canonical JSON and versioned boundary codecs for PyWorkflowKit V2."""

from __future__ import annotations

import json
from typing import TypeVar, cast

from pydantic import ValidationError

from pyworkflowkit.diagnostics.failure import FailureEvidence
from pyworkflowkit.diagnostics.model import Diagnostic
from pyworkflowkit.lineage.model import RunManifest
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.evidence import RuntimeEvent, TaskOutputCheckpoint
from pyworkflowkit.runtime.references import ExternalRunRef, WorkflowExecutionReference
from pyworkflowkit.serialization.contracts import V2_BOUNDARY_WIRE_CONTRACTS
from pyworkflowkit.serialization.mapping import (
    correlation_context_from_schema,
    correlation_context_to_schema,
    diagnostic_from_schema,
    diagnostic_to_schema,
    external_run_ref_from_schema,
    external_run_ref_to_schema,
    failure_evidence_from_schema,
    failure_evidence_to_schema,
    run_manifest_from_schema,
    run_manifest_to_schema,
    runtime_event_from_schema,
    runtime_event_to_schema,
    task_output_checkpoint_from_schema,
    task_output_checkpoint_to_schema,
    workflow_execution_reference_from_schema,
    workflow_execution_reference_to_schema,
)
from pyworkflowkit.serialization.migration import (
    UnsupportedWireVersionError,
    WireMigrationRegistry,
)
from pyworkflowkit.serialization.schemas import (
    CorrelationContextSchema,
    DiagnosticSchema,
    ExternalRunRefSchema,
    FailureEvidenceSchema,
    RunManifestSchema,
    RuntimeEventSchema,
    StrictSchema,
    TaskOutputCheckpointSchema,
    WireEnvelope,
    WorkflowExecutionReferenceSchema,
    portable_json_value,
)

SchemaT = TypeVar("SchemaT", bound=StrictSchema)
BoundaryT = TypeVar("BoundaryT")
BoundaryValue = (
    CorrelationContext
    | WorkflowExecutionReference
    | ExternalRunRef
    | FailureEvidence
    | Diagnostic
    | RuntimeEvent
    | TaskOutputCheckpoint
    | RunManifest
)

DEFAULT_MAX_WIRE_BYTES = 1_048_576


class WireContractError(ValueError):
    """Raised when a payload cannot satisfy the canonical V2 wire contract."""


class WirePayloadTooLargeError(WireContractError):
    """Raised before decoding a payload larger than the configured boundary."""


class WireContractMismatchError(WireContractError):
    """Raised when contract identity, version or expected domain type is inconsistent."""


class SchemaCodec:
    """Canonical deterministic JSON codec for StrictSchema values."""

    @staticmethod
    def to_dict(schema: StrictSchema) -> dict[str, object]:
        if not isinstance(schema, StrictSchema):
            raise TypeError("schema must be a StrictSchema")
        return cast(dict[str, object], schema.model_dump(mode="json"))

    @staticmethod
    def to_json(schema: StrictSchema) -> str:
        return canonical_json(SchemaCodec.to_dict(schema))

    @staticmethod
    def to_bytes(schema: StrictSchema) -> bytes:
        return SchemaCodec.to_json(schema).encode("utf-8")

    @staticmethod
    def from_json(schema_type: type[SchemaT], payload: str | bytes) -> SchemaT:
        if not isinstance(payload, (str, bytes)):
            raise TypeError("payload must be str or bytes")
        return schema_type.model_validate_json(payload)

    @staticmethod
    def from_dict(schema_type: type[SchemaT], payload: dict[str, object]) -> SchemaT:
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        # Re-enter through JSON so strict schemas receive genuine JSON semantics
        # (for example arrays decoded into declared tuple fields).
        return SchemaCodec.from_json(schema_type, canonical_json(payload))


def canonical_json(value: object) -> str:
    """Encode strict portable JSON with stable UTF-8/canonical ordering semantics."""

    normalized = portable_json_value(value, path="value")
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class BoundaryCodec:
    """Version-aware non-executable codec for the canonical V2 boundary values."""

    def __init__(
        self,
        *,
        migrations: WireMigrationRegistry | None = None,
        max_payload_bytes: int = DEFAULT_MAX_WIRE_BYTES,
    ) -> None:
        if isinstance(max_payload_bytes, bool) or not isinstance(max_payload_bytes, int):
            raise TypeError("max_payload_bytes must be an integer")
        if max_payload_bytes < 1:
            raise ValueError("max_payload_bytes must be greater than or equal to 1")
        self._migrations = migrations or WireMigrationRegistry()
        self._max_payload_bytes = max_payload_bytes

    @property
    def max_payload_bytes(self) -> int:
        return self._max_payload_bytes

    def encode(self, value: BoundaryValue) -> str:
        contract_key, schema = _schema_for_value(value)
        descriptor = V2_BOUNDARY_WIRE_CONTRACTS[contract_key]
        _validate_embedded_version(
            schema,
            expected_version=descriptor.contract_version,
        )
        envelope = WireEnvelope(
            contract=descriptor.contract,
            contract_version=descriptor.contract_version,
            payload=SchemaCodec.to_dict(schema),
        )
        encoded = SchemaCodec.to_json(envelope)
        self._enforce_size(encoded.encode("utf-8"))
        return encoded

    def encode_bytes(self, value: BoundaryValue) -> bytes:
        return self.encode(value).encode("utf-8")

    def decode(self, payload: str | bytes) -> BoundaryValue:
        raw = _wire_bytes(payload)
        self._enforce_size(raw)
        try:
            envelope = SchemaCodec.from_json(WireEnvelope, raw)
        except (ValidationError, ValueError, TypeError) as exc:
            raise WireContractError("invalid V2 wire envelope") from exc

        contract_key = _contract_key_for_id(envelope.contract)
        descriptor = V2_BOUNDARY_WIRE_CONTRACTS[contract_key]
        if envelope.contract_version != descriptor.contract_version:
            envelope = self._migrations.upgrade(
                envelope,
                target_version=descriptor.contract_version,
            )

        try:
            value = _value_from_envelope(contract_key, envelope)
        except (ValidationError, ValueError, TypeError) as exc:
            raise WireContractError(
                f"invalid payload for contract {descriptor.contract!r}"
            ) from exc
        return value

    def decode_as(
        self,
        expected_type: type[BoundaryT],
        payload: str | bytes,
    ) -> BoundaryT:
        value = self.decode(payload)
        if not isinstance(value, expected_type):
            raise WireContractMismatchError(
                f"wire payload decoded as {type(value).__name__}, "
                f"expected {expected_type.__name__}"
            )
        return value

    def _enforce_size(self, payload: bytes) -> None:
        if len(payload) > self._max_payload_bytes:
            raise WirePayloadTooLargeError(
                f"wire payload has {len(payload)} bytes; "
                f"limit is {self._max_payload_bytes}"
            )


def _wire_bytes(payload: str | bytes) -> bytes:
    if isinstance(payload, bytes):
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WireContractError("wire payload must be valid UTF-8") from exc
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    raise TypeError("payload must be str or bytes")


def _schema_for_value(value: BoundaryValue) -> tuple[str, StrictSchema]:
    if isinstance(value, CorrelationContext):
        return "correlation_context", correlation_context_to_schema(value)
    if isinstance(value, WorkflowExecutionReference):
        return (
            "workflow_execution_reference",
            workflow_execution_reference_to_schema(value),
        )
    if isinstance(value, ExternalRunRef):
        return "external_run_ref", external_run_ref_to_schema(value)
    if isinstance(value, FailureEvidence):
        return "failure_evidence", failure_evidence_to_schema(value)
    if isinstance(value, Diagnostic):
        return "diagnostic", diagnostic_to_schema(value)
    if isinstance(value, RuntimeEvent):
        return "runtime_event", runtime_event_to_schema(value)
    if isinstance(value, TaskOutputCheckpoint):
        return "task_output_checkpoint", task_output_checkpoint_to_schema(value)
    if isinstance(value, RunManifest):
        return "run_manifest", run_manifest_to_schema(value)
    raise TypeError(f"unsupported V2 boundary value {type(value).__name__}")


def _contract_key_for_id(contract: str) -> str:
    matches = [
        key
        for key, descriptor in V2_BOUNDARY_WIRE_CONTRACTS.items()
        if descriptor.contract == contract
    ]
    if len(matches) != 1:
        raise WireContractMismatchError(f"unknown V2 wire contract {contract!r}")
    return matches[0]


def _value_from_envelope(
    contract_key: str,
    envelope: WireEnvelope,
) -> BoundaryValue:
    descriptor = V2_BOUNDARY_WIRE_CONTRACTS[contract_key]
    if envelope.contract != descriptor.contract:
        raise WireContractMismatchError("wire contract identity changed during migration")
    if envelope.contract_version != descriptor.contract_version:
        raise UnsupportedWireVersionError(
            f"unsupported wire version {envelope.contract_version!r} "
            f"for {envelope.contract!r}"
        )

    payload = cast(dict[str, object], envelope.payload)

    if contract_key == "correlation_context":
        return correlation_context_from_schema(
            SchemaCodec.from_dict(CorrelationContextSchema, payload)
        )
    if contract_key == "workflow_execution_reference":
        schema = SchemaCodec.from_dict(WorkflowExecutionReferenceSchema, payload)
        _validate_embedded_version(schema, expected_version=descriptor.contract_version)
        return workflow_execution_reference_from_schema(schema)
    if contract_key == "external_run_ref":
        schema = SchemaCodec.from_dict(ExternalRunRefSchema, payload)
        _validate_embedded_version(schema, expected_version=descriptor.contract_version)
        return external_run_ref_from_schema(schema)
    if contract_key == "failure_evidence":
        schema = SchemaCodec.from_dict(FailureEvidenceSchema, payload)
        _validate_embedded_version(schema, expected_version=descriptor.contract_version)
        return failure_evidence_from_schema(schema)
    if contract_key == "diagnostic":
        return diagnostic_from_schema(SchemaCodec.from_dict(DiagnosticSchema, payload))
    if contract_key == "runtime_event":
        return runtime_event_from_schema(
            SchemaCodec.from_dict(RuntimeEventSchema, payload)
        )
    if contract_key == "task_output_checkpoint":
        return task_output_checkpoint_from_schema(
            SchemaCodec.from_dict(TaskOutputCheckpointSchema, payload)
        )
    if contract_key == "run_manifest":
        return run_manifest_from_schema(
            SchemaCodec.from_dict(RunManifestSchema, payload)
        )

    raise WireContractMismatchError(f"unsupported V2 wire contract key {contract_key!r}")


def _validate_embedded_version(
    schema: StrictSchema,
    *,
    expected_version: str,
) -> None:
    embedded = getattr(schema, "contract_version", expected_version)
    if embedded != expected_version:
        raise WireContractMismatchError(
            f"payload contract_version {embedded!r} does not match "
            f"wire version {expected_version!r}"
        )


__all__ = [
    "BoundaryCodec",
    "BoundaryValue",
    "DEFAULT_MAX_WIRE_BYTES",
    "SchemaCodec",
    "WireContractError",
    "WireContractMismatchError",
    "WirePayloadTooLargeError",
    "canonical_json",
]
