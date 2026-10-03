"""LOT-15 tests for explicit directed wire migrations."""

from __future__ import annotations

import pytest

from pyworkflowkit.runtime import CorrelationContext
from pyworkflowkit.serialization import (
    BoundaryCodec,
    DuplicateWireMigrationError,
    UnsupportedWireVersionError,
    WireEnvelope,
    WireMigrationRegistry,
)


def test_wire_migration_registry_applies_deterministic_multi_step_path() -> None:
    registry = WireMigrationRegistry()
    registry.register(
        contract="example.contract",
        from_version="1",
        to_version="2",
        migrator=lambda payload: {**payload, "v2": True},
    )
    registry.register(
        contract="example.contract",
        from_version="2",
        to_version="3",
        migrator=lambda payload: {**payload, "v3": True},
    )

    upgraded = registry.upgrade(
        WireEnvelope(
            contract="example.contract",
            contract_version="1",
            payload={"value": 1},
        ),
        target_version="3",
    )

    assert upgraded == WireEnvelope(
        contract="example.contract",
        contract_version="3",
        payload={"value": 1, "v2": True, "v3": True},
    )


def test_wire_migration_registry_does_not_create_implicit_reverse_edge() -> None:
    registry = WireMigrationRegistry()
    registry.register(
        contract="example.contract",
        from_version="1",
        to_version="2",
        migrator=lambda payload: payload,
    )

    with pytest.raises(UnsupportedWireVersionError, match="no explicit migration path"):
        registry.upgrade(
            WireEnvelope(
                contract="example.contract",
                contract_version="2",
                payload={"value": 1},
            ),
            target_version="1",
        )


def test_wire_migration_registry_rejects_duplicate_and_identity_edges() -> None:
    registry = WireMigrationRegistry()
    registry.register(
        contract="example.contract",
        from_version="1",
        to_version="2",
        migrator=lambda payload: payload,
    )

    with pytest.raises(DuplicateWireMigrationError, match="already exists"):
        registry.register(
            contract="example.contract",
            from_version="1",
            to_version="2",
            migrator=lambda payload: payload,
        )

    with pytest.raises(ValueError, match="must change"):
        registry.register(
            contract="example.contract",
            from_version="1",
            to_version="1",
            migrator=lambda payload: payload,
        )


def test_wire_migration_registry_rejects_invalid_migrator_result() -> None:
    registry = WireMigrationRegistry()
    registry.register(
        contract="example.contract",
        from_version="1",
        to_version="2",
        migrator=lambda payload: "bad",  # type: ignore[return-value]
    )

    with pytest.raises(TypeError, match="must return"):
        registry.upgrade(
            WireEnvelope(
                contract="example.contract",
                contract_version="1",
                payload={"value": 1},
            ),
            target_version="2",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("contract", ""),
        ("from_version", ""),
        ("to_version", ""),
    ),
)
def test_wire_migration_registry_rejects_blank_identity_fields(
    field: str,
    value: str,
) -> None:
    registry = WireMigrationRegistry()
    kwargs = {
        "contract": "example.contract",
        "from_version": "1",
        "to_version": "2",
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=field):
        registry.register(
            contract=kwargs["contract"],
            from_version=kwargs["from_version"],
            to_version=kwargs["to_version"],
            migrator=lambda payload: payload,
        )



def test_boundary_codec_requires_explicit_registered_upcast() -> None:
    registry = WireMigrationRegistry()
    registry.register(
        contract="pykit.correlation_context",
        from_version="0",
        to_version="1",
        migrator=lambda payload: {
            "correlation_id": payload["correlation"],
        },
    )
    codec = BoundaryCodec(migrations=registry)
    legacy = (
        '{"contract":"pykit.correlation_context","contract_version":"0",'
        '"payload":{"correlation":"C-legacy"}}'
    )

    restored = codec.decode_as(CorrelationContext, legacy)

    assert str(restored.correlation_id) == "C-legacy"
    assert codec.encode(restored) == (
        '{"contract":"pykit.correlation_context","contract_version":"1",'
        '"payload":{"causation_id":null,"correlation_id":"C-legacy",'
        '"ingestion_run_id":null,"parent_execution_id":null,"span_id":null,'
        '"task_attempt_id":null,"task_run_id":null,"trace_id":null,'
        '"transformation_execution_id":null,"workflow_run_id":null}}'
    )
