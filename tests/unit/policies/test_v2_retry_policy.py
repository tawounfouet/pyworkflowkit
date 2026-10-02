"""LOT-07 unit tests for V2 RetryPolicy and RetryEvaluator."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pyworkflowkit.diagnostics import (
    FailureCategory,
    FailureEvidence,
    OutcomeUncertainty,
    Retryability,
)
from pyworkflowkit.policies import (
    BackoffStrategy,
    RetryDecision,
    RetryEvaluation,
    RetryEvaluator,
    RetryJitter,
    RetryJitterSource,
    RetryPolicy,
    SystemRetryJitterSource,
)
from pyworkflowkit.runtime import CorrelationId


class HalfJitter:
    def full_jitter(self, upper_bound_seconds: float) -> float:
        return upper_bound_seconds / 2


def _failure(
    *,
    category: FailureCategory = FailureCategory.TRANSIENT,
    retryability: Retryability = Retryability.RETRYABLE,
    uncertainty: OutcomeUncertainty = OutcomeUncertainty.KNOWN,
) -> FailureEvidence:
    return FailureEvidence(
        error_code="E-RETRY",
        category=category,
        retryability=retryability,
        uncertainty=uncertainty,
        correlation_id=CorrelationId.parse("C-RETRY"),
        occurred_at=datetime(2026, 10, 2, 16, 0, tzinfo=UTC),
    )


def test_retry_policy_defaults_to_one_attempt_without_delay() -> None:
    policy = RetryPolicy()

    assert policy.max_attempts == 1
    assert policy.backoff_strategy is BackoffStrategy.NONE
    assert policy.initial_delay_seconds == 0
    assert policy.max_delay_seconds is None
    assert policy.jitter is RetryJitter.NONE
    assert policy.retryable_failure_categories == frozenset()
    assert policy.total_budget_seconds is None
    assert policy.reconciliation_required is True


@pytest.mark.parametrize(
    ("kwargs", "error"),
    (
        ({"max_attempts": 0}, ValueError),
        ({"max_attempts": True}, TypeError),
        ({"initial_delay_seconds": -1.0}, ValueError),
        ({"initial_delay_seconds": float("inf")}, ValueError),
        ({"max_delay_seconds": -1.0}, ValueError),
        ({"total_budget_seconds": -1.0}, ValueError),
        ({"jitter": "full"}, TypeError),
        ({"reconciliation_required": 1}, TypeError),
        ({"retryable_failure_categories": frozenset({"transient"})}, TypeError),
    ),
)
def test_retry_policy_rejects_invalid_values(
    kwargs: dict[str, object],
    error: type[Exception],
) -> None:
    with pytest.raises(error):
        RetryPolicy(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("strategy", "attempt_number", "expected"),
    (
        (BackoffStrategy.NONE, 1, 0.0),
        (BackoffStrategy.FIXED, 1, 2.0),
        (BackoffStrategy.FIXED, 3, 2.0),
        (BackoffStrategy.LINEAR, 1, 2.0),
        (BackoffStrategy.LINEAR, 3, 6.0),
        (BackoffStrategy.EXPONENTIAL, 1, 2.0),
        (BackoffStrategy.EXPONENTIAL, 2, 4.0),
        (BackoffStrategy.EXPONENTIAL, 3, 8.0),
    ),
)
def test_backoff_strategies_are_attempt_scoped(
    strategy: BackoffStrategy,
    attempt_number: int,
    expected: float,
) -> None:
    evaluation = RetryEvaluator().evaluate(
        policy=RetryPolicy(
            max_attempts=5,
            backoff_strategy=strategy,
            initial_delay_seconds=2.0,
        ),
        failure=_failure(),
        attempt_number=attempt_number,
        elapsed_seconds=0.0,
    )

    assert evaluation.decision is RetryDecision.RETRY
    assert evaluation.delay_seconds == expected


def test_max_delay_caps_backoff_before_jitter() -> None:
    evaluation = RetryEvaluator(jitter_source=HalfJitter()).evaluate(
        policy=RetryPolicy(
            max_attempts=5,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            initial_delay_seconds=10.0,
            max_delay_seconds=12.0,
            jitter=RetryJitter.FULL,
        ),
        failure=_failure(),
        attempt_number=3,
        elapsed_seconds=0.0,
    )

    assert evaluation.delay_seconds == 6.0


def test_retry_evaluator_uses_structured_retryability_not_message_text() -> None:
    failure = _failure(retryability=Retryability.NON_RETRYABLE)

    evaluation = RetryEvaluator().evaluate(
        policy=RetryPolicy(max_attempts=4),
        failure=failure,
        attempt_number=1,
        elapsed_seconds=0.0,
    )

    assert evaluation.decision is RetryDecision.DO_NOT_RETRY
    assert evaluation.reason == "failure_marked_non_retryable"


def test_retry_evaluator_fails_closed_when_retryability_is_unknown() -> None:
    evaluation = RetryEvaluator().evaluate(
        policy=RetryPolicy(max_attempts=4),
        failure=_failure(retryability=Retryability.UNKNOWN),
        attempt_number=1,
        elapsed_seconds=0.0,
    )

    assert evaluation.decision is RetryDecision.DO_NOT_RETRY
    assert evaluation.reason == "retryability_unknown"


def test_retryable_category_allowlist_is_structured() -> None:
    evaluation = RetryEvaluator().evaluate(
        policy=RetryPolicy(
            max_attempts=4,
            retryable_failure_categories=frozenset({FailureCategory.RATE_LIMITED}),
        ),
        failure=_failure(category=FailureCategory.TRANSIENT),
        attempt_number=1,
        elapsed_seconds=0.0,
    )

    assert evaluation.decision is RetryDecision.DO_NOT_RETRY
    assert evaluation.reason == "failure_category_not_retryable"


def test_max_attempts_stops_retry_before_new_attempt() -> None:
    evaluation = RetryEvaluator().evaluate(
        policy=RetryPolicy(max_attempts=2),
        failure=_failure(),
        attempt_number=2,
        elapsed_seconds=0.0,
    )

    assert evaluation.decision is RetryDecision.DO_NOT_RETRY
    assert evaluation.reason == "max_attempts_exhausted"


def test_total_budget_accounts_for_computed_delay() -> None:
    evaluation = RetryEvaluator().evaluate(
        policy=RetryPolicy(
            max_attempts=4,
            backoff_strategy=BackoffStrategy.FIXED,
            initial_delay_seconds=3.0,
            total_budget_seconds=5.0,
        ),
        failure=_failure(),
        attempt_number=1,
        elapsed_seconds=3.0,
    )

    assert evaluation.decision is RetryDecision.DO_NOT_RETRY
    assert evaluation.reason == "retry_budget_exhausted"
    assert evaluation.budget_remaining_seconds == 2.0


@pytest.mark.parametrize(
    ("required", "expected"),
    (
        (True, RetryDecision.RECONCILE),
        (False, RetryDecision.ESCALATE),
    ),
)
def test_uncertain_outcome_is_never_blindly_retried(
    required: bool,
    expected: RetryDecision,
) -> None:
    evaluation = RetryEvaluator().evaluate(
        policy=RetryPolicy(
            max_attempts=5,
            reconciliation_required=required,
        ),
        failure=_failure(
            category=FailureCategory.UNKNOWN_OUTCOME,
            retryability=Retryability.RETRYABLE_AFTER_RECONCILIATION,
            uncertainty=OutcomeUncertainty.REQUIRES_RECONCILIATION,
        ),
        attempt_number=1,
        elapsed_seconds=0.0,
    )

    assert evaluation.decision is expected
    assert evaluation.delay_seconds == 0


def test_retry_jitter_source_protocol_is_runtime_checkable() -> None:
    source = HalfJitter()

    assert isinstance(source, RetryJitterSource)



def test_system_jitter_source_validates_bounds_and_zero() -> None:
    source = SystemRetryJitterSource()

    assert source.full_jitter(0.0) == 0.0
    value = source.full_jitter(1.0)
    assert 0.0 <= value <= 1.0

    with pytest.raises(TypeError):
        source.full_jitter(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="finite"):
        source.full_jitter(float("inf"))
    with pytest.raises(ValueError, match="greater than or equal"):
        source.full_jitter(-1.0)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        ("decision", "retry", TypeError),
        ("reason", "", ValueError),
        ("delay_seconds", -1.0, ValueError),
        ("attempt_number", True, TypeError),
        ("attempt_number", 0, ValueError),
        ("max_attempts", True, TypeError),
        ("max_attempts", 0, ValueError),
        ("failure_category", "transient", TypeError),
        ("retryability", "retryable", TypeError),
        ("uncertainty", "known", TypeError),
        ("budget_remaining_seconds", -1.0, ValueError),
    ),
)
def test_retry_evaluation_rejects_invalid_boundary_values(
    field: str,
    value: object,
    error: type[Exception],
) -> None:
    values: dict[str, object] = {
        "decision": RetryDecision.RETRY,
        "reason": "retryable",
        "delay_seconds": 0.0,
        "attempt_number": 1,
        "max_attempts": 2,
        "failure_category": FailureCategory.TRANSIENT,
        "retryability": Retryability.RETRYABLE,
        "uncertainty": OutcomeUncertainty.KNOWN,
        "budget_remaining_seconds": None,
    }
    values[field] = value

    with pytest.raises(error):
        RetryEvaluation(**values)  # type: ignore[arg-type]


def test_retry_evaluator_rejects_invalid_dependencies_and_inputs() -> None:
    with pytest.raises(TypeError, match="jitter_source"):
        RetryEvaluator(jitter_source=object())  # type: ignore[arg-type]

    evaluator = RetryEvaluator()

    with pytest.raises(TypeError, match="policy"):
        evaluator.evaluate(
            policy=object(),  # type: ignore[arg-type]
            failure=_failure(),
            attempt_number=1,
            elapsed_seconds=0.0,
        )
    with pytest.raises(TypeError, match="failure"):
        evaluator.evaluate(
            policy=RetryPolicy(),
            failure=object(),  # type: ignore[arg-type]
            attempt_number=1,
            elapsed_seconds=0.0,
        )
    with pytest.raises(TypeError, match="attempt_number"):
        evaluator.evaluate(
            policy=RetryPolicy(),
            failure=_failure(),
            attempt_number=True,
            elapsed_seconds=0.0,
        )
    with pytest.raises(ValueError, match="attempt_number"):
        evaluator.evaluate(
            policy=RetryPolicy(),
            failure=_failure(),
            attempt_number=0,
            elapsed_seconds=0.0,
        )
    with pytest.raises(ValueError, match="elapsed_seconds"):
        evaluator.evaluate(
            policy=RetryPolicy(),
            failure=_failure(),
            attempt_number=1,
            elapsed_seconds=-1.0,
        )


class OvershootingJitter:
    def full_jitter(self, upper_bound_seconds: float) -> float:
        return upper_bound_seconds + 1.0


class NegativeJitter:
    def full_jitter(self, upper_bound_seconds: float) -> float:
        return -1.0


@pytest.mark.parametrize(
    ("source", "message"),
    (
        (OvershootingJitter(), "upper bound"),
        (NegativeJitter(), "greater than or equal"),
    ),
)
def test_retry_evaluator_rejects_invalid_injected_jitter(
    source: RetryJitterSource,
    message: str,
) -> None:
    evaluator = RetryEvaluator(jitter_source=source)
    policy = RetryPolicy(
        max_attempts=2,
        backoff_strategy=BackoffStrategy.FIXED,
        initial_delay_seconds=1.0,
        jitter=RetryJitter.FULL,
    )

    with pytest.raises(ValueError, match=message):
        evaluator.evaluate(
            policy=policy,
            failure=_failure(),
            attempt_number=1,
            elapsed_seconds=0.0,
        )
