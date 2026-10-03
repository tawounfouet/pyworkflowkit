"""Canonical versioned JSON codec for V2 boundary values."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, TypeAlias, TypeVar, cast

from pydantic import ValidationError

from pyworkflowkit.diagnostics.failure import FailureEvidence
from pyworkflowkit.diagnostics.model import Diagnostic
from pyworkflowkit.errors import PyWorkflowKitError
from pyworkflowkit.runtime.context import CorrelationContext
from pyworkflowkit.runtime.references import ExternalRunRef, WorkflowExecutionReference
from pyworkflowkit.serialization.contracts import (
    V2_BOUNDARY_WIRE_CONTRACTS,
    WireContractDescriptor,
)
from pyworkflowkit.serialization.mapping import (
    BoundaryValue,
    schema_for_value,
    value_from_schema,
)
from pyworkflowkit.serialization.schemas import (
    CorrelationContextSchema,
    DiagnosticSchema,
    ExternalRunRefSchema,
    FailureEvidenceSchema,
    StrictBoundarySchema,
    WireEnvelopeSchema,
    WorkflowExecutionReferenceSchema,
)

DEFAULT_MAX_PAYLOAD_BYTES = 1_048_576
DEFAULT_MAX_NESTING_DEPTH = 32

SchemaType: TypeAlias = type[StrictBoundarySchema]
BoundaryType: TypeAlias = (
    type[CorrelationContext]
    | type[WorkflowExecutionReference]
    | type[ExternalRunRef]
    | type[FailureEvidence]
    | type[Diagnostic]
)
Upcaster: TypeAlias = Callable[[Mapping[str, object]], Mapping[str, object]]
BoundaryT = TypeVar("BoundaryT", bound=BoundaryValue)


class WireContractError(PyWorkflowKitError):
    """Raised when a wire payload violates the qualified V2 contract."""


@dataclass(frozen=True, slots=True)
class BoundaryContractSpec:
    """Static non-executable binding between one wire identity and one V2 type."""

    descriptor: WireContractDescriptor
    value_type: BoundaryType
    schema_type: SchemaType


_SPECS_BY_NAME: Mapping[str, BoundaryContractSpec] = MappingProxyType(
    {
        "correlation_context": BoundaryContractSpec(
            descriptor=V2_BOUNDARY_WIRE_CONTRACTS["correlation_context"],
            value_type=CorrelationContext,
            schema_type=CorrelationContextSchema,
        ),
        "diagnostic": BoundaryContractSpec(
            descriptor=V2_BOUNDARY_WIRE_CONTRACTS["diagnostic"],
            value_type=Diagnostic,
            schema_type=DiagnosticSchema,
        ),
        "external_run_ref": BoundaryContractSpec(
            descriptor=V2_BOUNDARY_WIRE_CONTRACTS["external_run_ref"],
            value_type=ExternalRunRef,
            schema_type=ExternalRunRefSchema,
        ),
        "failure_evidence": BoundaryContractSpec(
            descriptor=V2_BOUNDARY_WIRE_CONTRACTS["failure_evidence"],
            value_type=FailureEvidence,
            schema_type=FailureEvidenceSchema,
        ),
        "workflow_execution_reference": BoundaryContractSpec(
            descriptor=V2_BOUNDARY_WIRE_CONTRACTS["workflow_execution_reference"],
            value_type=WorkflowExecutionReference,
            schema_type=WorkflowExecutionReferenceSchema,
        ),
    }
)
_SPECS_BY_CONTRACT: Mapping[str, BoundaryContractSpec] = MappingProxyType(
    {spec.descriptor.contract: spec for spec in _SPECS_BY_NAME.values()}
)
_SPECS_BY_TYPE: Mapping[BoundaryType, BoundaryContractSpec] = MappingProxyType(
    {spec.value_type: spec for spec in _SPECS_BY_NAME.values()}
)


class BoundaryUpcasterRegistry:
    """Explicit deterministic migration hooks between wire contract versions."""

    def __init__(self) -> None:
        self._steps: dict[tuple[str, str], tuple[str, Upcaster]] = {}

    def register(
        self,
        *,
        contract: str,
        from_version: str,
        to_version: str,
        upcaster: Upcaster,
    ) -> None:
        for field_name, value in (
            ("contract", contract),
            ("from_version", from_version),
            ("to_version", to_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must not be blank")
        if from_version == to_version:
            raise ValueError("upcaster source and target versions must differ")
        if not callable(upcaster):
            raise TypeError("upcaster must be callable")
        key = (contract, from_version)
        if key in self._steps:
            raise ValueError(
                f"upcaster already registered for {contract!r} version {from_version!r}"
            )
        self._steps[key] = (to_version, upcaster)

    def upcast(
        self,
        *,
        contract: str,
        from_version: str,
        to_version: str,
        payload: Mapping[str, object],
    ) -> dict[str, object]:
        current_version = from_version
        current_payload = dict(payload)
        seen: set[str] = set()

        for _ in range(32):
            if current_version == to_version:
                return current_payload
            if current_version in seen:
                raise WireContractError(f"upcaster cycle detected for contract {contract!r}")
            seen.add(current_version)

            step = self._steps.get((contract, current_version))
            if step is None:
                raise WireContractError(
                    f"no upcaster from {contract!r} version {current_version!r} to {to_version!r}"
                )
            next_version, upcaster = step
            migrated = upcaster(MappingProxyType(dict(current_payload)))
            if not isinstance(migrated, Mapping):
                raise WireContractError("upcaster must return a mapping")
            current_payload = dict(migrated)
            current_version = next_version

        raise WireContractError(f"upcaster chain for contract {contract!r} exceeds 32 steps")


class BoundaryWireCodec:
    """Canonical non-executable JSON codec for qualified V2 boundary values."""

    def __init__(
        self,
        *,
        max_payload_bytes: int = DEFAULT_MAX_PAYLOAD_BYTES,
        max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
        upcasters: BoundaryUpcasterRegistry | None = None,
    ) -> None:
        if isinstance(max_payload_bytes, bool) or not isinstance(max_payload_bytes, int):
            raise TypeError("max_payload_bytes must be an integer")
        if max_payload_bytes < 1:
            raise ValueError("max_payload_bytes must be greater than or equal to 1")
        if isinstance(max_nesting_depth, bool) or not isinstance(max_nesting_depth, int):
            raise TypeError("max_nesting_depth must be an integer")
        if max_nesting_depth < 1:
            raise ValueError("max_nesting_depth must be greater than or equal to 1")

        self._max_payload_bytes = max_payload_bytes
        self._max_nesting_depth = max_nesting_depth
        self._upcasters = upcasters or BoundaryUpcasterRegistry()

    @property
    def max_payload_bytes(self) -> int:
        return self._max_payload_bytes

    @property
    def max_nesting_depth(self) -> int:
        return self._max_nesting_depth

    @property
    def upcasters(self) -> BoundaryUpcasterRegistry:
        return self._upcasters

    def encode(self, value: BoundaryValue) -> str:
        spec = _SPECS_BY_TYPE.get(type(value))
        if spec is None:
            raise WireContractError(f"unsupported boundary value type {type(value).__name__!r}")

        domain_version = getattr(value, "contract_version", spec.descriptor.contract_version)
        if domain_version != spec.descriptor.contract_version:
            raise WireContractError(
                f"{spec.descriptor.contract!r} value declares contract_version "
                f"{domain_version!r}; expected {spec.descriptor.contract_version!r}"
            )

        schema = schema_for_value(value)
        envelope = WireEnvelopeSchema(
            contract=spec.descriptor.contract,
            contract_version=spec.descriptor.contract_version,
            payload=cast(
                dict[str, Any],
                schema.model_dump(mode="json", exclude_none=True),
            ),
        )
        plain = envelope.model_dump(mode="json")
        _validate_nesting(plain, max_depth=self._max_nesting_depth)
        encoded = _canonical_json(plain)
        self._validate_size(encoded.encode("utf-8"))
        return encoded

    def encode_bytes(self, value: BoundaryValue) -> bytes:
        return self.encode(value).encode("utf-8")

    def decode(self, payload: str | bytes) -> BoundaryValue:
        raw_bytes = _to_utf8_bytes(payload)
        self._validate_size(raw_bytes)
        parsed = _strict_json_loads(raw_bytes)
        _validate_nesting(parsed, max_depth=self._max_nesting_depth)

        try:
            envelope = WireEnvelopeSchema.model_validate(parsed)
        except ValidationError as exc:
            raise WireContractError(f"invalid wire envelope: {exc}") from exc

        spec = _SPECS_BY_CONTRACT.get(envelope.contract)
        if spec is None:
            raise WireContractError(f"unknown boundary contract {envelope.contract!r}")

        body = dict(envelope.payload)
        if envelope.contract_version != spec.descriptor.contract_version:
            body = self._upcasters.upcast(
                contract=envelope.contract,
                from_version=envelope.contract_version,
                to_version=spec.descriptor.contract_version,
                payload=body,
            )
            _validate_nesting(body, max_depth=self._max_nesting_depth)

        try:
            schema = spec.schema_type.model_validate(body)
        except ValidationError as exc:
            raise WireContractError(f"invalid {spec.descriptor.contract!r} payload: {exc}") from exc

        value = value_from_schema(schema)
        declared_version = getattr(
            value,
            "contract_version",
            spec.descriptor.contract_version,
        )
        if declared_version != spec.descriptor.contract_version:
            raise WireContractError(
                f"decoded {spec.descriptor.contract!r} payload declares "
                f"contract_version {declared_version!r}; expected "
                f"{spec.descriptor.contract_version!r}"
            )
        return value

    def decode_as(self, expected_type: type[BoundaryT], payload: str | bytes) -> BoundaryT:
        value = self.decode(payload)
        if type(value) is not expected_type:
            raise WireContractError(
                f"decoded {type(value).__name__}, expected {expected_type.__name__}"
            )
        return cast(BoundaryT, value)

    def canonicalize(self, payload: str | bytes) -> str:
        """Validate/upcast a payload and return current canonical JSON."""

        return self.encode(self.decode(payload))

    def _validate_size(self, payload: bytes) -> None:
        if len(payload) > self._max_payload_bytes:
            raise WireContractError(f"wire payload exceeds {self._max_payload_bytes} byte limit")


def boundary_contract_specs() -> Mapping[str, BoundaryContractSpec]:
    """Return the immutable qualified LOT-15 contract registry."""

    return _SPECS_BY_NAME


def _to_utf8_bytes(payload: str | bytes) -> bytes:
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, bytes):
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WireContractError("wire payload must be valid UTF-8") from exc
        return payload
    raise TypeError("payload must be str or bytes")


def _strict_json_loads(payload: bytes) -> object:
    text = payload.decode("utf-8")
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
        )
    except (json.JSONDecodeError, _DuplicateKeyError) as exc:
        raise WireContractError(f"invalid canonical JSON: {exc}") from exc


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str) -> object:
    raise WireContractError(f"non-finite JSON constant {value!r} is not portable")


def _validate_nesting(value: object, *, max_depth: int, depth: int = 1) -> None:
    if depth > max_depth:
        raise WireContractError(f"wire payload exceeds maximum nesting depth {max_depth}")
    if isinstance(value, Mapping):
        for nested in value.values():
            _validate_nesting(nested, max_depth=max_depth, depth=depth + 1)
    elif isinstance(value, list):
        for nested in value:
            _validate_nesting(nested, max_depth=max_depth, depth=depth + 1)


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise WireContractError("wire value is not canonical JSON portable") from exc


__all__ = [
    "BoundaryContractSpec",
    "BoundaryUpcasterRegistry",
    "BoundaryWireCodec",
    "DEFAULT_MAX_NESTING_DEPTH",
    "DEFAULT_MAX_PAYLOAD_BYTES",
    "WireContractError",
    "boundary_contract_specs",
]
