"""Tests covering edge cases and validation logic in CorrelationContext."""

from __future__ import annotations

import pytest

from pyworkflowkit.runtime.context import CorrelationContext


def test_correlation_context_type_validation() -> None:
    # Invalid correlation_id type
    with pytest.raises(TypeError, match="correlation_id must be a CorrelationId"):
        CorrelationContext(correlation_id="not-a-correlation-id")  # type: ignore[arg-type]

    # Non-string optional fields
    with pytest.raises(ValueError, match="causation_id must be a non-empty string"):
        CorrelationContext(causation_id="")

    with pytest.raises(ValueError, match="causation_id must be a non-empty string"):
        CorrelationContext(causation_id="   ")

    with pytest.raises(ValueError, match="traceparent must be a non-empty string"):
        CorrelationContext(traceparent="")

    with pytest.raises(ValueError, match="tracestate must be a non-empty string"):
        CorrelationContext(tracestate="  ")

    # Invalid baggage types
    with pytest.raises(TypeError, match="baggage must be a dict"):
        CorrelationContext(baggage="not-a-dict")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="baggage keys and values must be strings"):
        CorrelationContext(baggage={1: "value"})  # type: ignore[dict-item]

    with pytest.raises(TypeError, match="baggage keys and values must be strings"):
        CorrelationContext(baggage={"key": 123})  # type: ignore[dict-item]


def test_correlation_context_with_trace_auto_traceparent() -> None:
    ctx = CorrelationContext()
    # Auto compute traceparent
    traced = ctx.with_trace(
        trace_id="4bf92f3577b34da6a3ce929d0e0e4736",
        span_id="00f067aa0ba902b7",
        baggage={"user.id": "42"},
        tracestate="congo=t61rcWkgMzE",
    )
    assert traced.traceparent == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    assert traced.tracestate == "congo=t61rcWkgMzE"
    assert traced.baggage == {"user.id": "42"}


def test_correlation_context_with_w3c_trace_variations() -> None:
    ctx = CorrelationContext()

    # Well-formed W3C header
    traced_ok = ctx.with_w3c_trace(
        traceparent="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        tracestate="rojo=1",
        baggage={"env": "prod"},
    )
    assert traced_ok.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert traced_ok.span_id == "00f067aa0ba902b7"
    assert traced_ok.tracestate == "rojo=1"
    assert traced_ok.baggage == {"env": "prod"}

    # Malformed traceparent fallback (less than 4 parts)
    traced_short = ctx.with_w3c_trace(traceparent="invalid-traceparent")
    assert traced_short.trace_id is None
    assert traced_short.span_id is None
    assert traced_short.traceparent == "invalid-traceparent"
